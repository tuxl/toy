#-*- coding:utf-8 -*-
#监控文件 并自动重启进程
"""
使用方法
python3 codewatcher.py 监控目录路径 要监控的文件扩展名多个扩展名逗号分隔 要运行的程序执行命令
eg:
python3 codewatcher.py /tem .py,.java "mycommand arg1 arg2 arg3"
"""
import sys
import abc
import os
import time
import subprocess
import argparse
import re

E_CHANGE_FILENAME = 0X1     #包括文件创建 删除 重命名事件
E_CHANGE_DIRNAME = 0X2      #包括文件夹创建 删除 重命名事件
E_WRITE = 0X3               #文件写入事件

RELOAD_INTERVAL_TIME = 2

class ProcessManager():

    def __init__(self, command):
        self.command = command
        self.startProcess()

    def startProcess(self):
        platformStr = sys.platform
        if 'win32' in platformStr:
            sh = True
        else:
            sh = False
        self._proc = subprocess.Popen(self.command, shell=sh)

    def stopProcess(self):
        platformStr = sys.platform
        if 'win32' in platformStr:
            #windows必须用这种方式来结束进程
            subprocess.call(['taskkill', '/F', '/T', '/PID', str(self._proc.pid)])
        else:
            self._proc.terminate()


    def reload(self):
        if self._proc.poll() == None:
            #进程尚未停止
            self.stopProcess()
            times = 60
            while times > 0:
                if self._proc.poll() != None:
                    self.startProcess()
                    break
                time.sleep(1)
                times -= 1
        else:
            self.startProcess()


class EventWatcher(metaclass=abc.ABCMeta):

    def __init__(self, path, fileExt):
        self.watchPath = path
        self.fileExt = fileExt

    @abc.abstractmethod
    def registEvent(self, event):
        pass

    def setManager(self, manager):
        """
        设置进程管理器
        """
        self.manager = manager

    @abc.abstractmethod
    def startWatch(self):
        pass

def genWinWatcher():
    import win32file
    import win32con
    class WinWatcher(EventWatcher):

        def __init__(self, *args, **kwargs):
            super(WinWatcher,self).__init__(*args,**kwargs)

        def registEvent(self, event):
            event2watch = 0x0
            if E_CHANGE_FILENAME & event:
                event2watch = event2watch | win32con.FILE_NOTIFY_CHANGE_FILE_NAME
            if E_CHANGE_DIRNAME & event:
                event2watch = event2watch | win32con.FILE_NOTIFY_CHANGE_DIR_NAME
            if E_WRITE & event:
                event2watch = event2watch | win32con.FILE_NOTIFY_CHANGE_SIZE

            self.event2watch = event2watch


        def makeHandle(self):
            FILE_LIST_DIRECTORY = 0x0001
            hDir = win32file.CreateFile(
                self.watchPath,
                FILE_LIST_DIRECTORY,
                win32con.FILE_SHARE_READ |
                win32con.FILE_SHARE_WRITE |
                win32con.FILE_SHARE_DELETE,
                None,
                win32con.OPEN_EXISTING,
                win32con.FILE_FLAG_BACKUP_SEMANTICS,
                None
            )
            return hDir

        def needReload(self, file):
            """
            如果文件扩展名在监控的扩展名内
            或
            文件没有扩展名 则返回 true
            """
            _, ext = os.path.splitext(file)
            if ext in self.fileExt:
                return True
            elif ext == '':
                return True
            return False

        def startWatch(self):
            lastReloadTime = time.time()
            while True:
                results = win32file.ReadDirectoryChangesW(
                    self.makeHandle(),
                    1024,
                    True,
                    self.event2watch,
                    None,
                    None
                )
                for action, file in results:
                    if (time.time() - lastReloadTime) < RELOAD_INTERVAL_TIME:
                        #进程重启时间间隔不能小于2s
                        break
                    if self.fileExt == False or self.needReload(file):
                        self.manager.reload()
                        lastReloadTime = time.time()
                        break
    return WinWatcher

def genLinuxWatcher():
    import pyinotify

    class EventHandler(pyinotify.ProcessEvent):

        def __init__(self, manager, fext):
            self.manager = manager
            self.lastReload = time.time()
            self.fileExt = fext
            super(EventHandler, self).__init__()

        def process_IN_MOVED_FROM(self, event):
            self.reactEvent(event)

        def process_IN_MOVED_TO(self, event):
            self.reactEvent(event)

        def process_IN_CREATE(self, event):
            self.reactEvent(event)

        def process_IN_DELETE(self, event):
            self.reactEvent(event)

        def process_IN_MODIFY(self, event):
            self.reactEvent(event)

        def reactEvent(self, event):
            if (time.time() - self.lastReload) < RELOAD_INTERVAL_TIME:
                #重启时间间隔要大于最小重启间隔周期
                return
            if self.fileExt == False or self.needReload(event.pathname):
                self.manager.reload()
                self.lastReload = time.time()

        def needReload(self, file):
            """
            如果文件扩展名在监控的扩展名内
            或
            文件没有扩展名 则返回 true
            """
            _, ext = os.path.splitext(file)
            if ext in self.fileExt:
                return True
            elif ext == '':
                return True
            else:
                return False

    class LinuxWatcher(EventWatcher):
        def __init__(self, *args, **kwargs):
            super(LinuxWatcher, self).__init__(*args, **kwargs)

        def registEvent(self, event):
            event2watch = 0x0
            if E_CHANGE_FILENAME & event or E_CHANGE_DIRNAME & event:
                event2watch = event2watch | pyinotify.IN_MOVED_FROM | \
                              pyinotify.IN_MOVED_TO | pyinotify.IN_CREATE | \
                              pyinotify.IN_DELETE
            if E_WRITE & event:
                event2watch = event2watch | pyinotify.IN_MODIFY

            self.event2watch = event2watch

        def startWatch(self):
            handler = EventHandler(self.manager, self.fileExt)
            wm = pyinotify.WatchManager()
            wdd = wm.add_watch(self.watchPath, self.event2watch, rec=True)
            notifier = pyinotify.Notifier(wm, handler)
            notifier.loop()

    return LinuxWatcher

def genWatcherCls():
    """
    根据不同平台创建不同的watcher
    """
    platformStr = sys.platform
    if 'win32' in platformStr:
        return genWinWatcher()
    elif 'linux' in platformStr:
        return genLinuxWatcher()
    else:
        return None


def parseCommand():
    '''
    解析命令行参数
    '''
    parser = argparse.ArgumentParser()
    parser.add_argument('target', help='要监控的文件或目录')
    parser.add_argument('extlist', help='要监控的文件名后缀')
    parser.add_argument('programe', help='程序启动命令')
    args = parser.parse_args()
    return args

def parseExtList(extstr):
    #如果是* 表示不过滤扩展名
    if extstr == '*':
        return False
    else:
        extlist = extstr.split(',')
        extlist = [i for i in filter(lambda item: item != '', extlist)]
        return extlist


if __name__ == '__main__':
    args = parseCommand()
    target = args.target
    if os.path.exists(target) == False:
        print('目标文件不存在')
        exit(1)
    extlist = parseExtList(args.extlist)
    command = args.programe
    command = re.split(r'\s+', command)
    watcherCls = genWatcherCls()
    watcher = watcherCls(target, extlist)
    watcher.registEvent(E_CHANGE_FILENAME | E_CHANGE_DIRNAME | E_WRITE)
    pmanager = ProcessManager(command)
    watcher.setManager(pmanager)
    watcher.startWatch()