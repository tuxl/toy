#!/bin/bash
#代码同步脚本
set -x
set -e
# 要同步的主机
hosts=(
'192.168.195.201 root 123456'
'192.168.195.202 root 123456'
)
# 要同步的文件或文件夹 
# !!!文件夹最后面不要带斜杠!!!
files=(
'/root/scptest'
'/root/main.cpp'
)

function getDir(){
    dirname=`echo $1 | awk -F '/' '{dir=""};{
        for(i=1; i<NF; i++){
            dir = dir $i "/"
        }
    };{print dir}'`
    echo $dirname
}

function doscp(){
    expect -c "
    spawn $1
    expect {
        \"*(yes/no)?\" { send \"yes\r\";exp_continue }
        \"*password\" { send  \"$2\r\" }
    }
    interact
    "
}


function transfile(){
    for((i=0; i<${#files[@]}; i++)){
        
        if [[ -d ${files[i]} ]]
        then
            local dir=`getDir ${files[i]}` 
            local cmd="scp -r ${files[i]} ${2}@${1}:$dir"
            doscp "$cmd" $3
        else
            local cmd="scp ${files[i]} ${2}@${1}:${files[i]}"
            doscp "$cmd" $3
        fi
    }
}


for((i=0; i<${#hosts[@]}; i++))
do
    authinfo=(`echo ${hosts[$i]} | awk '{print $1, $2, $3}'`)
    transfile ${authinfo[0]} ${authinfo[1]} ${authinfo[2]}
done

