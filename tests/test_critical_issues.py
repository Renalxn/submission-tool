# -*- coding: utf-8 -*-
"""
测试 Critical 级别问题的修复

这些测试应该在修复前失败（红灯），修复后通过（绿灯）。
"""
import pytest
import os
import stat
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestShellInjection:
    """测试 Shell 注入漏洞修复（问题 #1）"""
    
    def test_open_folder_with_single_quote_in_path(self, tmp_path):
        """测试路径中包含单引号时是否能正确处理"""
        # 创建一个带单引号的目录名
        test_dir = tmp_path / "it's a test"
        test_dir.mkdir()
        
        # 导入被测模块
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from app import App
        
        # 创建应用实例（会创建 Tk 窗口）
        # 注意：这会在测试时显示窗口，可能需要手动关闭
        try:
            app = App()
        except Exception:
            pytest.skip("无法创建 App 实例（可能需要显示环境）")
        
        # Mock subprocess.run 来验证调用方式
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            # 调用 open_folder
            app.open_folder(str(test_dir))
            
            # 验证使用了 subprocess.run 而不是 os.system
            # 并且参数是列表形式（不经过 shell 解析）
            assert mock_run.called, "应该使用 subprocess.run"
            call_args = mock_run.call_args[0][0]
            assert isinstance(call_args, list), "参数应该是列表，而不是字符串"
            assert str(test_dir) in call_args, "路径应该在参数列表中"
    
    def test_open_folder_with_special_characters(self, tmp_path):
        """测试路径中包含特殊字符时是否能正确处理"""
        # 创建包含各种特殊字符的目录
        test_dir = tmp_path / "test&dir;with$special"
        test_dir.mkdir()
        
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from app import App
        
        app = App(None)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            app.open_folder(str(test_dir))
            
            # 验证没有使用 shell=True
            if mock_run.called:
                call_kwargs = mock_run.call_args[1] if len(mock_run.call_args) > 1 else {}
                assert not call_kwargs.get('shell', False), "不应该使用 shell=True"


class TestKeyFilePermissions:
    """测试密钥文件权限修复（问题 #2）"""
    
    def test_key_file_permissions_on_unix(self, tmp_path):
        """测试在 Unix 系统上密钥文件权限是否为 0600"""
        # 跳过 Windows
        if os.name == 'nt':
            pytest.skip("此测试仅适用于 Unix 系统")
        
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        
        # 修改配置目录为临时目录
        with patch('app.CONFIG_DIR', tmp_path):
            with patch('app.KEY_FILE', tmp_path / 'key.bin'):
                with patch('app.CONFIG_FILE', tmp_path / 'config.enc'):
                    from app import get_cipher
                    
                    # 第一次调用会创建密钥
                    cipher = get_cipher()
                    
                    # 检查密钥文件权限
                    key_file = tmp_path / 'key.bin'
                    assert key_file.exists(), "密钥文件应该已创建"
                    
                    file_stat = os.stat(key_file)
                    file_mode = file_stat.st_mode
                    
                    # 检查权限：应该只有所有者可读写
                    assert file_mode & stat.S_IRUSR, "所有者应该有读权限"
                    assert file_mode & stat.S_IWUSR, "所有者应该有写权限"
                    assert not (file_mode & stat.S_IRGRP), "组用户不应该有读权限"
                    assert not (file_mode & stat.S_IROTH), "其他用户不应该有读权限"


class TestConfigDirCreation:
    """测试配置目录按需创建（问题 #3）"""
    
    def test_import_does_not_create_config_dir(self, tmp_path):
        """测试导入模块时不会自动创建配置目录"""
        import sys
        
        # 设置一个不存在的配置目录
        fake_config_dir = tmp_path / "nonexistent" / ".tougao_assistant"
        
        with patch('app.CONFIG_DIR', fake_config_dir):
            # 重新导入模块
            if 'app' in sys.modules:
                del sys.modules['app']
            
            # 导入模块
            sys.path.insert(0, str(Path(__file__).parent.parent))
            import app
            
            # 验证配置目录没有被创建
            assert not fake_config_dir.exists(), \
                "导入模块时不应该自动创建配置目录"
    
    def test_config_dir_created_on_demand(self, tmp_path):
        """测试配置目录在需要时才创建"""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        
        fake_config_dir = tmp_path / ".tougao_assistant"
        
        with patch('app.CONFIG_DIR', fake_config_dir):
            with patch('app.KEY_FILE', fake_config_dir / 'key.bin'):
                with patch('app.CONFIG_FILE', fake_config_dir / 'config.enc'):
                    from app import get_cipher
                    
                    # 调用需要配置目录的函数
                    get_cipher()
                    
                    # 验证配置目录被创建
                    assert fake_config_dir.exists(), \
                        "调用 get_cipher() 时应该创建配置目录"


class TestLoadConfigErrorHandling:
    """测试 load_config 的错误处理（问题 #5）"""
    
    def test_load_config_with_corrupted_file(self, tmp_path):
        """测试配置文件损坏时应该有提示而不是静默失败"""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        
        config_file = tmp_path / 'config.enc'
        key_file = tmp_path / 'key.bin'
        
        # 创建一个损坏的配置文件
        config_file.write_bytes(b"corrupted data")
        
        # 创建一个有效的密钥
        from cryptography.fernet import Fernet
        key = Fernet.generate_key()
        key_file.write_bytes(key)
        
        with patch('app.CONFIG_FILE', config_file):
            with patch('app.KEY_FILE', key_file):
                from app import load_config
                
                # 应该抛出异常或返回特定标识，而不是静默返回默认值
                with pytest.raises(Exception) as exc_info:
                    load_config()
                
                # 验证异常信息包含"配置"或"损坏"等关键词
                assert "配置" in str(exc_info.value) or "损坏" in str(exc_info.value) \
                    or "decrypt" in str(exc_info.value).lower()


class TestUnsupportedFileType:
    """测试不支持的文件类型处理（问题 #7）"""
    
    def test_read_full_text_with_unsupported_extension(self, tmp_path):
        """测试读取不支持的文件格式时应该抛出异常"""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        
        # 创建一个 .xyz 文件
        test_file = tmp_path / "test.xyz"
        test_file.write_text("test content", encoding="utf-8")
        
        from app import SubmissionToolApp
        app = SubmissionToolApp(None)
        
        # 应该抛出 ValueError 或类似异常
        with pytest.raises((ValueError, NotImplementedError)) as exc_info:
            app.read_full_text(str(test_file))
        
        # 验证异常信息提到文件格式
        assert "格式" in str(exc_info.value) or "支持" in str(exc_info.value) \
            or "extension" in str(exc_info.value).lower()
    
    def test_parse_file_with_unsupported_extension(self, tmp_path):
        """测试解析不支持的文件格式时应该抛出异常"""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        
        test_file = tmp_path / "test.xyz"
        test_file.write_text("test\ncontent", encoding="utf-8")
        
        from app import SubmissionToolApp
        app = SubmissionToolApp(None)
        
        with pytest.raises((ValueError, NotImplementedError)):
            app.parse_file(str(test_file))
