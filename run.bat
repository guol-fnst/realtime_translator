@echo off
echo 启动实时日语翻译字幕...
echo.

REM 激活虚拟环境
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

python src\main.py %*
