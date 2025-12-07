@echo off
echo ========================================
echo  实时日语转中文字幕翻译系统 - 安装脚本
echo ========================================
echo.

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

echo [1/3] 创建虚拟环境...
python -m venv venv
if errorlevel 1 (
    echo [警告] 创建虚拟环境失败，将使用全局Python环境
) else (
    call venv\Scripts\activate.bat
)

echo.
echo [2/3] 安装依赖...
pip install -r requirements.txt
if errorlevel 1 (
    echo [警告] 部分依赖安装失败
)

echo.
echo [3/3] 安装PyInstaller (用于打包)...
pip install pyinstaller
if errorlevel 1 (
    echo [警告] PyInstaller安装失败
)

echo.
echo ========================================
echo  安装完成!
echo ========================================
echo.
echo 运行方式:
echo   python src\main.py
echo.
echo 测试API连接:
echo   python src\main.py --test-api
echo.
echo 测试音频捕获:
echo   python src\main.py --test-audio
echo.
echo 打包为独立程序:
echo   build.bat
echo.
pause
