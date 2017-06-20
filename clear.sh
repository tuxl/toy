#!/bin/sh
#递归删除目标文件夹下的指定后缀的文件
set -e
# set -x

targetdir=$1
suffix=$2

if [ "$targetdir" = ''  ]
then
    echo "请指定目录"
    exit
fi

if [ "$suffix" = ''  ]
then
    echo "请指定后缀名"
    exit
fi

if [ ! -d $targetdir ]
then
    echo "$targetdir 不是一个目录"
    exit
fi

cleardir(){
    path=$1
    suf=$2
    for file in $path/*
    do
        # echo $file
        if [ -d $file ]
        then
            cleardir $file $suf
        else
            right=${file##*.}
            if [ $right = $suf ]
            then
                rm -f $file
            fi
        fi
    done
}

cleardir  $targetdir $suffix
