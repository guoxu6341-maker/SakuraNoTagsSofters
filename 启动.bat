@echo off
chcp 65001 >nul
title Sakura TagSofter 启动器

echo ==========================================
echo      正在启动 Sakura TagSofter...
echo ==========================================

cd /d "%~dp0"

:: 1. 检查是否安装了依赖 (可选，防止报错)
if not exist "venv" (
    echo 正在检查环境...
)

:: 2. 自动打开浏览器
echo 正在打开浏览器...
start http://127.0.0.1:5000

:: 3. 启动 Flask 后端
echo 正在启动后台服务...
python app.py

:: 如果程序崩溃，暂停显示错误信息
pause