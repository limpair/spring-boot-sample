#!/bin/bash

usage() {
    echo "salt-entrypoint.sh:"
    echo ""
    echo "    -M |--method     运行模式"
    echo "    -N |--name       服务名称"
    echo "    -AU|--app-url    服务程序包所在地址"
    echo "    -P|--app-path    服务程序包所在目录"
    echo "    -SU|--shell-url  启动脚本所在地址"
    echo "    -T |--token      获取程序包或脚本的Token"
    echo "    -D |--wrok-dir   脚本执行目录"
}

for arg in "$@"
do
    case $arg in
        -M|--method)     METHOD="$2";            shift 2        ;;
        -N|--name)       APP_NAME="$2";          shift 2        ;;
        -AU|--app-url)   APP_URL="$2";           shift 2        ;;
        -P|--app-path)   APP_PATH="$2";          shift 2        ;;
        -SU|--shell-url) SHELL_URL="$2";         shift 2        ;;
        -T|--token)      TOKEN="$2";             shift 2        ;;
        -D|--work-dir)   WORK_DIR="$2";          shift 2        ;;
        -H|--help|?)     usage;                  shift 2        ;;
    esac
done
set -x
init() {
    mkdir -p $WORK_DIR
    rm -rf $WORK_DIR/*
}
downloadFile (){
    cd $WORK_DIR
    wget $APP_URL?token=$TOKEN -O $APP_NAME
    #wget $SHELL_URL?token=$TOKEN
}
start() {
    cd $WORK_DIR
    java $JAVA_OPTS -Djava.security.egd=file:/dev/./urandom -jar $APP_NAME.jar > /var/log/$APP_NAME.log 2>&1 &
}
stop() {
    kill -9 $(ps aux | grep java | grep demo | grep -v entrypoint | awk '{print $2}')
}
status() {
    RUN=`ps aux | grep java | grep demo | grep -v entrypoint | wc -l`
    if [ $RUN -gt 0 ]
    then
        echo 'is ok'
        exit 0
    else
        echo 'not ok'
        exit 1
    fi
}

case $METHOD in
    start|upgrade) stop; init; downloadFile; start ;;
    restart)       stop; start                     ;;
    status)        status
esac
