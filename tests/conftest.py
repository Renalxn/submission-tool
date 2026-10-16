# -*- coding: utf-8 -*-
"""
测试配置和公共工具
"""
import pytest
import tempfile
import shutil
from pathlib import Path


@pytest.fixture
def temp_dir():
    """创建临时测试目录"""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    # 清理
    if temp_path.exists():
        shutil.rmtree(temp_path)


@pytest.fixture
def sample_txt_file(temp_dir):
    """创建示例 TXT 文件"""
    file_path = temp_dir / "test_article.txt"
    file_path.write_text(
        "测试标题\n"
        "测试作者\n"
        "这是正文第一行\n"
        "这是正文第二行\n",
        encoding="utf-8"
    )
    return file_path


@pytest.fixture
def sample_md_file(temp_dir):
    """创建示例 Markdown 文件"""
    file_path = temp_dir / "test_article.md"
    file_path.write_text(
        "# 测试标题\n"
        "测试作者\n"
        "这是正文第一行\n"
        "这是正文第二行\n",
        encoding="utf-8"
    )
    return file_path
