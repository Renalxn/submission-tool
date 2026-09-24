#!/bin/bash
# 投稿排版助手 v1.0 启动脚本 (macOS / Linux)

echo "========================================"
echo "  投稿排版助手 v1.0"
echo "========================================"
echo ""

# Check Python3
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python3，请先安装 Python 3.10+"
    echo "   macOS:  brew install python3"
    echo "   Linux:  sudo apt install python3 python3-pip"
    exit 1
fi

# Check dependencies
if ! python3 -c "import streamlit" 2>/dev/null; then
    echo "📦 首次运行，正在安装依赖..."
    pip3 install streamlit python-docx markdown
fi

echo "✅ 启动投稿排版助手..."
echo ""
echo "🌐 请在浏览器中打开：http://localhost:8501"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
streamlit run "$SCRIPT_DIR/app.py" --server.headless true --server.port 8501
