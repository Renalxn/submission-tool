# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for 投稿排版助手
Usage:
  Windows: pyinstaller subtool.spec
  macOS:   pyinstaller subtool.spec
  Linux:   pyinstaller subtool.spec
"""

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('docs/用户手册.txt', 'docs')],  # 打包用户手册
    hiddenimports=[
        'docx',
        'docx.shared',
        'docx.enum',
        'docx.enum.text',
        'docx.oxml',
        'docx.oxml.ns',
        'cryptography',
        'cryptography.fernet',
    ],
    hookspath=['hooks'],  # 添加自定义钩子路径
    hooksconfig={},
    runtime_hooks=['hooks/extract_manual.py'],  # 运行时钩子：释放用户手册
    excludes=['streamlit', 'markdown'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='投稿排版助手_v1.0.41',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
