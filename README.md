# 投稿排版助手 v1.0

纯本地桌面工具（Tkinter GUI），自动将文章按规范格式排版为 .docx 和 .txt 文件。不联网，纯本地运行。

## 功能

- 选择 .docx / .txt / .md 文件（.doc 格式会提示另存为）
- 自动识别标题、作者填入界面，可手动修改
- 按投稿规范排版：宋体；标题4号、居中；作者姓名5号、居中；正文5号、两端对齐、首行缩进两格、单倍行距
- 自动统计正文字数，显示"（正文：xxx 字）"
- 联系信息（姓名/微信/电话/地址/邮编/身份证号/邮箱）自动记忆，下次打开自动填入
- 银行信息最多4组，可添加/删除，加密保存到本地
- 同时生成 .docx 和 .txt 两种输出格式

## 快速启动

### Windows
pip install python-docx cryptography
python app.py

### macOS / Linux
pip3 install python-docx cryptography
python3 app.py

## 依赖
- Python 3.10+
- python-docx
- cryptography

## 文件约定
输入文件结构：
- 第 1 行 = 文章标题
- 第 2 行 = 作者姓名
- 第 3 行起 = 正文

## 输出
在用户选择的目录下自动创建《文章标题》投稿子文件夹，包含：
- 《文章标题》作者姓名.docx
- 《文章标题》作者姓名.txt

## 配置文件
联系信息和银行信息加密保存在 ~/.tougao_assistant/ 目录下，下次打开自动填入。

## 打包为可执行文件（给不懂编程的用户）
需先安装 PyInstaller：
pip install pyinstaller
pyinstaller submission_tool.spec
生成的可执行文件在 dist/投稿排版助手/ 目录下。

### 各平台打包
- Windows：在 Windows 上运行 pyinstaller submission_tool.spec
- macOS：在 macOS 上运行 pyinstaller submission_tool.spec
- Linux：在 Linux 上运行 pyinstaller submission_tool.spec

> PyInstaller 不支持交叉编译，需在目标平台上打包。
