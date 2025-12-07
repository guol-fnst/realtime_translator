@echo off
echo ========================================
echo  实时日语转中文字幕翻译系统 - 打包脚本
echo ========================================
echo.

REM 激活虚拟环境
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

echo [1/2] 清理旧文件...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

echo.
echo [2/2] 打包程序...
pyinstaller --noconfirm --onefile --windowed ^
    --name "JapaneseTranslator" ^
    --paths src ^
    --collect-all numpy ^
    --hidden-import config ^
    --hidden-import audio_capture ^
    --hidden-import speech_recognition ^
    --hidden-import translator ^
    --hidden-import subtitle_overlay ^
    --hidden-import sharing_server ^
    --hidden-import gpu_monitor ^
    --hidden-import pynvml ^
    --hidden-import websockets ^
    src\main.py

if errorlevel 1 (
    echo [错误] 打包失败
    pause
    exit /b 1
)

echo.
echo ========================================
echo  打包完成!
echo ========================================
echo.
echo 可执行文件位置: dist\JapaneseTranslator.exe
echo.
echo 注意: 首次运行可能需要较长时间解压
echo.
pause
