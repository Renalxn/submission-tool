# 投稿排版助手 v1.0

纯本地投稿排版工具，自动将文章按规范格式排版为 .docx 和 .txt 文件。

## 功能

- 支持 .docx / .txt / .md 三种输入格式（.doc 不支持）
- 自动识别标题、作者、正文
- 按投稿规范排版输出：宋体、字号、对齐、段首空两格
- 自动统计正文字数
- 联系信息和银行信息自动记忆
- 同时生成 .docx 和 .txt 两种输出格式

## 快速启动

### Windows

双击 `start.bat`

### macOS / Linux

```bash
./start.sh
```

启动后浏览器自动打开 http://localhost:8501

### 手动启动

```bash
pip install streamlit python-docx markdown
streamlit run app.py
```

## 依赖

- Python 3.10+
- streamlit
- python-docx
- markdown

## 文件约定

输入文件结构：
- 第 1 行 = 文章标题
- 第 2 行 = 作者姓名
- 第 3 行起 = 正文

## 输出

在用户选择的目录下自动创建 `《文章标题》投稿` 子文件夹，包含：
- `《文章标题》作者姓名.docx`
- `《文章标题》作者姓名.txt`

## 配置文件

联系信息和银行信息自动保存在 `~/.config/submission_tool/config.json`，
下次打开自动填充。

## 打包为可执行文件（给不懂编程的用户）

需先安装 PyInstaller：

```bash
pip install pyinstaller
pyinstaller submission_tool.spec
```

生成的可执行文件在 `dist/投稿排版助手/` 目录下。

### 各平台打包

| 平台 | 操作系统 | 打包命令 |
|------|----------|----------|
| Windows | 在 Windows 上运行 | `pyinstaller submission_tool.spec` |
| macOS | 在 macOS 上运行 | `pyinstaller submission_tool.spec` |
| Linux | 在 Linux 上运行 | `pyinstaller submission_tool.spec` |

> ⚠️ PyInstaller 不支持交叉编译，需在目标平台上打包。
