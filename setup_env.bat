@echo off
echo 🔧 创建 Python 3.11 虚拟环境...
python -m venv venv

echo 📦 安装依赖...
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt

echo ✅ 虚拟环境创建完成！
echo.
echo 启动方式：
echo   1. 激活环境: venv\Scripts\activate.bat
echo   2. 运行程序: python main.py
pause
