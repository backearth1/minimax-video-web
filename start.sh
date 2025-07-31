#!/bin/bash

echo "🎬 启动 MiniMax Video Generation Tool"
echo "================================"

# 检查Python版本
python_version=$(python3 --version 2>&1 | grep -o '[0-9]\+\.[0-9]\+')
if [[ $(echo "$python_version < 3.8" | bc -l) -eq 1 ]]; then
    echo "❌ 需要Python 3.8或更高版本，当前版本: $python_version"
    exit 1
fi

# 检查是否存在虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "🔧 激活虚拟环境..."
source venv/bin/activate

# 安装依赖
echo "📥 安装依赖..."
pip install -r requirements.txt

# 创建必要目录
mkdir -p uploads static

# 启动服务
echo "🚀 启动服务..."
echo "📍 访问地址: http://localhost:8000"
echo "⏹️ 按 Ctrl+C 停止服务"
echo ""

python main.py