# 打包说明

本文档说明如何将投稿排版助手打包为独立的可执行文件。

## 前置要求

1. 安装 Python 3.10 或更高版本
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

## 打包步骤

### Windows

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
   dist/投稿排版助手/投稿排版助手.exe
   ```

### macOS

1. 打开终端
2. 进入项目目录：
   ```bash
   cd /path/to/submission-tool
   ```
3. 运行打包命令：
   ```bash
   pyinstaller subtool.spec
   ```
4. 打包完成后，可执行文件位于：
   ```
   dist/投稿排版助手/投稿排版助手
   ```

### Linux

1. 打开终端
2. 进入项目目录：
   ```bash
   cd /path/to/submission-tool
   ```
3. 运行打包命令：
   ```bash
   pyinstaller subtool.spec
   ```
4. 打包完成后，可执行文件位于：
   ```
   dist/投稿排版助手/投稿排版助手
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

将 `dist/投稿排版助手/` 整个文件夹压缩为 zip，发送给用户即可。

### macOS

将 `dist/投稿排版助手/` 压缩为 zip 或制作 .dmg 安装包。

### Linux

将 `dist/投稿排版助手/` 压缩为 tar.gz，或制作 .deb/.rpm 包。

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
