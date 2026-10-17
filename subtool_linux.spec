# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for 投稿排版助手 (Linux 专用)
Usage:
  Linux: pyinstaller subtool_linux.spec
  
输出：dist/投稿排版助手_v1.0.39/投稿排版助手_v1.0.39

注意：需要在真正的 Linux 环境中打包（不能在 WSL2 中）
"""

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[],
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
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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
    [],
    exclude_binaries=True,
    name='投稿排版助手_v1.0.39',
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

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='投稿排版助手_v1.0.39',
)
