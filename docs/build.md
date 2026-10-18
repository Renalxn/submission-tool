# 打包说明

本文档说明如何将投稿排版助手打包为独立的可执行文件。

## 前置要求

1. 安装 Python 3.10 或更高版本
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   pip install pyinstaller
   ```

## 打包步骤

### Windows（已完成 ✅）

1. 打开 PowerShell 或命令提示符
2. 进入项目目录：
   ```bash
   cd path\to\submission-tool
   ```
3. 运行打包命令：
   ```bash
   pyinstaller subtool.spec
   ```
4. 打包完成后，可执行文件位于：
   ```
   dist/投稿排版助手_v1.0.39.exe
   ```

### macOS（待办 🔄）

**注意：** 需要在 macOS 系统中打包，不能在 Windows 或 WSL2 中打包。

1. 打开终端
2. 进入项目目录：
   ```bash
   cd /path/to/submission-tool
   ```
3. 运行打包命令：
   ```bash
   pyinstaller subtool_macos.spec
   ```
4. 打包完成后，.app 包位于：
   ```
   dist/投稿排版助手_v1.0.39.app
   ```
5. 双击 .app 包即可运行

### Linux（可以做 ⏸️）

**注意：** 需要在真正的 Linux 环境中打包，不能在 WSL2 中打包（WSL2 无法打包 GUI 应用）。

1. 打开终端
2. 进入项目目录：
   ```bash
   cd /path/to/submission-tool
   ```
3. 运行打包命令：
   ```bash
   pyinstaller subtool_linux.spec
   ```
4. 打包完成后，可执行文件位于：
   ```
   dist/投稿排版助手_v1.0.39
   ```
5. 运行可执行文件：
   ```bash
   ./dist/投稿排版助手_v1.0.39
   ```

## 注意事项

1. **PyInstaller 不支持交叉编译**
   - Windows 上只能打包 Windows 版本
   - macOS 上只能打包 macOS 版本
   - Linux 上只能打包 Linux 版本

2. **首次运行可能较慢**
   - 首次启动时需要解压资源，可能需要几秒钟

3. **杀毒软件可能误报**
   - PyInstaller 打包的程序可能被杀毒软件误报
   - 这是正常现象，可以添加到白名单

4. **macOS 应用签名**
   - 如果要分发给其他用户，需要进行应用签名
   - 否则 macOS 会提示"无法验证开发者"

## 分发

### Windows

将 `dist/投稿排版助手_v1.0.39.exe` 发送给用户即可（单文件，无需解压）。

### macOS

将 `dist/投稿排版助手_v1.0.39.app` 压缩为 zip 或制作 .dmg 安装包。

### Linux

将 `dist/投稿排版助手_v1.0.39` 压缩为 tar.gz，或制作 .deb/.rpm 包。

## 故障排查

### 打包失败

- 确保所有依赖已安装：`pip install -r requirements.txt`
- 确保 Python 版本 >= 3.10
- 尝试清理后重新打包：
  ```bash
  rm -rf build dist
  pyinstaller subtool.spec
  ```

### 运行时报错

- 检查是否缺少依赖
- 查看 `build/` 目录下的日志文件
- 尝试在命令行运行可执行文件，查看错误信息
