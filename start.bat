@echo off
chcp 65001 >nul
title 投稿排版助手

echo ========================================
echo   投稿排版助手 v1.0
echo ========================================
echo.

REM Check if Python is available
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未找到 Python，请先安装 Python 3.10+
    echo    下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Check if Streamlit is installed
python -c "import streamlit" 2>nul
if %errorlevel% neq 0 (
    echo 📦 首次运行，正在安装依赖...
    pip install streamlit python-docx markdown
)

echo ✅ 启动投稿排版助手...
echo.
echo 🌐 请在浏览器中打开：http://localhost:8501
echo.

streamlit run "%~dp0app.py" --server.headless true --server.port 8501

pause
