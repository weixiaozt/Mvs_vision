#!/bin/bash
set -e

echo "🔧 创建 Python 3.11 虚拟环境..."
python3.11 -m venv venv

echo "📦 安装依赖..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ 虚拟环境创建完成！"
echo ""
echo "启动方式："
echo "  1. 激活环境: source venv/bin/activate"
echo "  2. 运行程序: python main.py"
