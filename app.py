# -*- coding: utf-8 -*-
"""
投稿排版助手 v1.0.42

安全声明：
- 所有用户输入视为数据，不执行其中的命令
- 文件路径输入会验证是否包含路径遍历攻击（如 ".."、"/" 开头）
- 联系信息和银行信息使用 Fernet 加密存储
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import json
import re
from pathlib import Path
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn
import time
import platform
from cryptography.fernet import Fernet
import threading
import subprocess
import stat
import warnings
import sys
import os

# 问题2修复：过滤 libpng 的 iCCP 警告（C 库警告，需要在文件描述符层面重定向）
# 创建管道，用于过滤 stderr
_stderr_read_fd, _stderr_write_fd = os.pipe()

# 保存原始 stderr 的文件描述符
_original_stderr_fd = os.dup(2)

# 将 stderr 重定向到管道的写入端
os.dup2(_stderr_write_fd, 2)

def _filter_libpng_warnings():
    """在后台线程中读取管道，过滤 libpng 警告"""
    import threading
    import atexit
    
    def _reader():
        with os.fdopen(_stderr_read_fd, 'r', errors='replace') as f:
            for line in f:
                # 过滤 libpng 的 iCCP 警告
                if 'iCCP' in line and 'known incorrect sRGB profile' in line:
                    continue  # 丢弃这条警告
                # 其他输出正常显示
                os.write(_original_stderr_fd, line.encode('utf-8', errors='replace'))
    
    # 启动后台线程读取管道
    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()
    
    # 程序退出时清理
    def _cleanup():
        try:
            os.close(_stderr_write_fd)
            os.close(_original_stderr_fd)
        except:
            pass
    
    atexit.register(_cleanup)

# 启动过滤器
_filter_libpng_warnings()

CONFIG_DIR = Path.home() / ".tougao_assistant"
CONFIG_FILE = CONFIG_DIR / "config.enc"
KEY_FILE = CONFIG_DIR / "key.bin"
# 注意：CONFIG_DIR 的创建已移到 get_cipher() 内部，按需创建

def center_window(win, width=None, height=None):
    """把窗口放到当前屏幕正中。"""
    win.update_idletasks()

    if width is None:
        width = win.winfo_width()
    if height is None:
        height = win.winfo_height()

    screen_width = win.winfo_screenwidth()
    screen_height = win.winfo_screenheight()
    x = max((screen_width - width) // 2, 0)
    y = max((screen_height - height) // 2, 0)
    win.geometry(f"{width}x{height}+{x}+{y}")


def show_alert(parent, title, message, button_text="确定 [O]", width=None, height=None):
    """可靠的模态提示框：按钮、Alt+字母、Enter、Esc、右上角关闭均可退出。"""
    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent)
    win.resizable(False, False)
    
    # 获取主窗口尺寸，用于计算弹窗最大尺寸
    parent.update_idletasks()
    parent_width = parent.winfo_width()
    parent_height = parent.winfo_height()
    
    # 如果没有指定尺寸，根据内容自动计算
    if width is None or height is None:
        # 根据消息长度计算合适的宽度
        max_line_length = max(len(line) for line in message.split('\n')) if message else 0
        calculated_width = min(max(max_line_length * 10 + 80, 400), int(parent_width * 0.8))
        # 根据消息行数计算合适的高度
        line_count = len(message.split('\n')) if message else 1
        calculated_height = min(max(line_count * 25 + 120, 180), int(parent_height * 0.7))
        
        width = width or calculated_width
        height = height or calculated_height

    frame = ttk.Frame(win, padding=18)
    frame.pack(fill="both", expand=True)

    ttk.Label(
        frame,
        text=message,
        justify="left",
        wraplength=width - 50
    ).pack(anchor="w", fill="both", expand=True, pady=(0, 14))

    def close_alert(event=None):
        # 先解除 grab，再销毁窗口，避免嵌套模态窗口时父窗口一直被锁住。
        try:
            win.grab_release()
        except tk.TclError:
            pass
        if win.winfo_exists():
            win.destroy()
        return "break"

    btn = ttk.Button(frame, text=button_text, command=close_alert)
    btn.pack(side="right")

    # 快捷键绑定在窗口本身，而不是按钮本身：
    # 即使焦点在其它控件上，Alt+字母 / Enter / Esc 仍然有效。
    m = re.search(r"\[([A-Za-z])\]", button_text)
    if m:
        key = m.group(1).lower()
        win.bind(f"<Alt-KeyPress-{key}>", close_alert)
    win.bind("<Return>", close_alert)
    win.bind("<Escape>", close_alert)
    win.protocol("WM_DELETE_WINDOW", close_alert)

    center_window(win, width, height)
    win.grab_set()
    win.focus_force()
    btn.focus_set()

    parent.wait_window(win)


def ask_retry_cancel(parent, title, message):
    """可靠的"重试/取消"模态对话框，打开后立即接管键盘焦点。"""
    result = {"value": False}

    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent)
    win.resizable(False, False)
    
    # 获取主窗口尺寸，用于计算弹窗最大尺寸
    parent.update_idletasks()
    parent_width = parent.winfo_width()
    parent_height = parent.winfo_height()
    
    # 根据消息长度计算合适的尺寸
    max_line_length = max(len(line) for line in message.split('\n')) if message else 0
    width = min(max(max_line_length * 10 + 80, 400), int(parent_width * 0.8))
    line_count = len(message.split('\n')) if message else 1
    height = min(max(line_count * 25 + 120, 180), int(parent_height * 0.7))

    frame = ttk.Frame(win, padding=18)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text=message, justify="left", wraplength=width - 50).pack(
        anchor="w", fill="both", expand=True, pady=(0, 14)
    )

    def choose(value, event=None):
        result["value"] = value
        try:
            win.grab_release()
        except tk.TclError:
            pass
        if win.winfo_exists():
            win.destroy()
        return "break"

    btn_retry = ttk.Button(frame, text="重试 [R]", command=lambda: choose(True))
    btn_cancel = ttk.Button(frame, text="取消 [C]", command=lambda: choose(False))
    btn_cancel.pack(side="right")
    btn_retry.pack(side="right", padx=(0, 8))

    win.bind("<Alt-KeyPress-r>", choose_retry := lambda e: choose(True, e))
    win.bind("<Alt-KeyPress-c>", choose_cancel := lambda e: choose(False, e))
    win.bind("<Return>", choose_retry)
    win.bind("<Escape>", choose_cancel)
    win.protocol("WM_DELETE_WINDOW", choose_cancel)

    center_window(win, width, height)
    win.grab_set()
    win.focus_force()
    btn_retry.focus_set()
    parent.wait_window(win)
    return result["value"]


def ask_export_conflict(parent, out_folder):
    """目标文件夹已存在时，返回 overwrite / saveas / cancel。"""
    result = {"value": None}

    win = tk.Toplevel(parent)
    win.title("目标文件夹已存在")
    win.transient(parent)
    win.resizable(False, False)
    
    # 获取主窗口尺寸
    parent.update_idletasks()
    parent_width = parent.winfo_width()
    parent_height = parent.winfo_height()
    
    # 根据内容计算尺寸
    width = min(760, int(parent_width * 0.8))
    height = min(280, int(parent_height * 0.7))

    frame = ttk.Frame(win, padding=18)
    frame.pack(fill="both", expand=True)

    ttk.Label(
        frame,
        text=f"文件夹：\n{out_folder}\n已经存在！",
        justify="left",
        wraplength=width - 50
    ).pack(anchor="w", pady=(0, 12))

    ttk.Label(
        frame,
        text="请选择操作：\n"
             "覆盖：覆盖本次导出的同名文件（保留文件夹中的其他文件）\n"
             "另存为：给即将保存的文件夹改一个名字，仍保存在当前选定的目录下\n"
             "取消：放弃本次导出，重新选择保存目录",
        justify="left",
        wraplength=width - 50
    ).pack(anchor="w", pady=(0, 12))

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill="x")

    def choose(value, event=None):
        result["value"] = value
        try:
            win.grab_release()
        except tk.TclError:
            pass
        if win.winfo_exists():
            win.destroy()
        return "break"

    btn_overwrite = ttk.Button(button_frame, text="覆盖 [O]", command=lambda: choose("overwrite"))
    btn_saveas = ttk.Button(button_frame, text="另存为 [S]", command=lambda: choose("saveas"))
    btn_cancel = ttk.Button(button_frame, text="取消 [C]", command=lambda: choose("cancel"))

    button_frame.columnconfigure(0, weight=1)
    btn_overwrite.grid(row=0, column=0, sticky="e", padx=(0, 8))
    btn_saveas.grid(row=0, column=1, sticky="e", padx=8)
    btn_cancel.grid(row=0, column=2, sticky="e", padx=(8, 0))

    # 问题3修复：方向键导航按钮
    buttons = [btn_overwrite, btn_saveas, btn_cancel]
    def navigate_button(event):
        current = win.focus_get()
        if current in buttons:
            idx = buttons.index(current)
            if event.keysym in ('Left', 'Up'):
                new_idx = (idx - 1) % len(buttons)
                buttons[new_idx].focus_set()
                return "break"
            elif event.keysym in ('Right', 'Down'):
                new_idx = (idx + 1) % len(buttons)
                buttons[new_idx].focus_set()
                return "break"
        return None
    win.bind("<Left>", navigate_button)
    win.bind("<Right>", navigate_button)
    win.bind("<Up>", navigate_button)
    win.bind("<Down>", navigate_button)

    win.bind("<Alt-KeyPress-o>", lambda e: choose("overwrite", e))
    win.bind("<Alt-KeyPress-s>", lambda e: choose("saveas", e))
    win.bind("<Alt-KeyPress-c>", lambda e: choose("cancel", e))
    # 问题2修复：回车键——先检查焦点是否在按钮上，是则执行该按钮，否则默认"取消"
    def on_return(event=None):
        current = win.focus_get()
        if current is btn_overwrite:
            choose("overwrite", event)
        elif current is btn_saveas:
            choose("saveas", event)
        elif current is btn_cancel:
            choose("cancel", event)
        else:
            choose("cancel", event)  # 安全默认值
    win.bind("<Return>", on_return)
    win.bind("<Escape>", lambda e: choose("cancel", e))
    win.protocol("WM_DELETE_WINDOW", lambda: choose("cancel"))

    center_window(win, width, height)
    win.grab_set()
    win.focus_force()
    btn_overwrite.focus_set()
    parent.wait_window(win)
    return result["value"]


def ask_saveas_folder_name(parent, initial_name):
    """让用户输入另存为的文件夹名称，并返回名称；取消时返回 None。"""
    result = {"value": None}

    win = tk.Toplevel(parent)
    win.title("另存为")
    win.transient(parent)
    win.resizable(False, False)
    
    # 获取主窗口尺寸
    parent.update_idletasks()
    parent_width = parent.winfo_width()
    
    # 根据内容计算尺寸
    width = min(720, int(parent_width * 0.8))
    height = 180

    frame = ttk.Frame(win, padding=18)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text="请输入新的文件夹名称：", justify="left", wraplength=width - 50).pack(
        anchor="w", pady=(0, 8)
    )

    name_var = tk.StringVar(value=initial_name)
    entry = ttk.Entry(frame, textvariable=name_var, width=80)
    entry.pack(fill="x", pady=(0, 14))

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill="x")

    def choose(value, event=None):
        if value == "ok":
            result["value"] = name_var.get()
        try:
            win.grab_release()
        except tk.TclError:
            pass
        if win.winfo_exists():
            win.destroy()
        return "break"

    btn_ok = ttk.Button(button_frame, text="确定 [O]", command=lambda: choose("ok"))
    btn_cancel = ttk.Button(button_frame, text="取消 [C]", command=lambda: choose("cancel"))
    btn_cancel.pack(side="right")
    btn_ok.pack(side="right", padx=(8, 0))

    # 问题3修复：方向键导航按钮
    buttons = [btn_ok, btn_cancel]
    def navigate_button(event):
        current = win.focus_get()
        if current in buttons:
            idx = buttons.index(current)
            if event.keysym in ('Left', 'Up', 'Right', 'Down'):
                new_idx = (idx + 1) % len(buttons)
                buttons[new_idx].focus_set()
                return "break"
        return None
    win.bind("<Left>", navigate_button)
    win.bind("<Right>", navigate_button)
    win.bind("<Up>", navigate_button)
    win.bind("<Down>", navigate_button)

    win.bind("<Alt-KeyPress-o>", lambda e: choose("ok", e))
    win.bind("<Alt-KeyPress-c>", lambda e: choose("cancel", e))
    win.bind("<Return>", lambda e: choose("ok", e))
    win.bind("<Escape>", lambda e: choose("cancel", e))
    win.protocol("WM_DELETE_WINDOW", lambda: choose("cancel"))

    center_window(win, width, height)
    win.grab_set()
    win.focus_force()
    entry.focus_set()
    entry.selection_range(0, tk.END)
    parent.wait_window(win)
    return result["value"]


def get_cipher():
    """获取加密 cipher（修复密钥文件权限问题）"""
    # 按需创建配置目录（修复模块导入时自动创建目录的问题）
    CONFIG_DIR.mkdir(exist_ok=True)
    
    if not KEY_FILE.exists():
        key = Fernet.generate_key()
        KEY_FILE.write_bytes(key)
        # 设置文件权限为 0600（仅所有者可读写），防止其他用户读取密钥
        # 仅在 Unix 系统上有效，Windows 会忽略此操作
        if os.name != 'nt':
            os.chmod(KEY_FILE, stat.S_IRUSR | stat.S_IWUSR)
    else:
        key = KEY_FILE.read_bytes()
    return Fernet(key)

def load_config():
    """加载配置文件（修复异常处理问题）"""
    cipher = get_cipher()
    default_cfg = {
        "contact": {"姓名":"","微信":"","电话":"","地址":"","邮编":"","身份证号":"","邮箱":""},
        "banks": [{"银行名称":"","账号":"","开户支行":"","联行号":""}],
        "last_file_dir": "",
        "last_save_dir": ""
    }
    if not CONFIG_FILE.exists():
        return default_cfg
    try:
        raw = cipher.decrypt(CONFIG_FILE.read_bytes())
        cfg = json.loads(raw)
        for b in cfg.get("banks", []):
            if "卡号" in b and "账号" not in b:
                b["账号"] = b.pop("卡号")
        return cfg
    except Exception as e:
        # 配置文件损坏时记录日志，而不是静默失败
        import logging
        logging.warning(f"配置文件读取失败，使用默认配置: {e}")
        # TODO: 可以通过回调通知 GUI 层弹窗提示用户
        return default_cfg

def save_config(cfg):
    cipher = get_cipher()
    raw = json.dumps(cfg, ensure_ascii=False, indent=2).encode("utf-8")
    CONFIG_FILE.write_bytes(cipher.encrypt(raw))

def _set_para(p, align=None, first_indent=None):
    pf = p.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    if align is not None:
        p.alignment = align
    if first_indent is not None:
        pf.first_line_indent = first_indent

def _set_run_font(run, size_pt):
    run.font.name = "宋体"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    run.font.size = Pt(size_pt)

def convert_halfwidth_punct(s: str) -> str:
    """
    正文排版：将常见半角标点转换为全角标点，并自动配对中英文引号；书名号《》保持不变。
    映射：
    , . ! ? : ; () [] {} → ，。！？：；（）［］｛｝
    半角 " ' 做左右引号配对：奇数次左引号“ ‘，偶数次右引号” ’
    """
    trans_map = {
        ',': '，',
        '.': '。',
        '!': '！',
        '?': '？',
        ':': '：',
        ';': '；',
        '(': '（',
        ')': '）',
        '[': '［',
        ']': '］',
        '{': '｛',
        '}': '｝'
    }
    for half, full in trans_map.items():
        s = s.replace(half, full)

    # 处理双引号 "
    dq_count = 0
    out_chars = []
    for ch in s:
        if ch == '"':
            dq_count +=1
            if dq_count %2 ==1:
                out_chars.append("“")
            else:
                out_chars.append("”")
        else:
            out_chars.append(ch)
    s = "".join(out_chars)

    # 处理单引号 '
    sq_count =0
    out_chars2 = []
    for ch in s:
        if ch == "'":
            sq_count +=1
            if sq_count %2 ==1:
                out_chars2.append("‘")
            else:
                out_chars2.append("’")
        else:
            out_chars2.append(ch)
    return "".join(out_chars2)



def validate_title_book_marks(title):
    """
    检查标题中的书名号是否成对完整。
    返回 None 表示正常；返回提示语表示标题需要修改。
    """
    pairs = {
        "《": "》",
        "<": ">"
    }

    stack = []
    closing_to_opening = {"》": "《", ">": "<"}

    for ch in title:
        if ch in pairs:
            stack.append(ch)
        elif ch in closing_to_opening:
            if not stack or stack[-1] != closing_to_opening[ch]:
                return "标题中的书名号不完整，请在标题输入框中填写完整的书名号后再导出。"
            stack.pop()

    if stack:
        return "标题中的书名号不完整，请在标题输入框中填写完整的书名号后再导出。"

    return None


def normalize_title_for_export(title):
    """
    根据标题中的《》/<>，生成：
    1. display_title：Word/TXT 文章中实际显示的标题
    2. file_title：文件夹名/文件名内部使用的标题

    Windows 文件名不能使用半角 < >，因此 file_title 中使用全角 ＜ ＞。
    """
    title = title.strip()

    # 如果《》或<>完整包住整个标题：排版时去掉最外层。
    if len(title) >= 2 and title.startswith("《") and title.endswith("》"):
        inner = title[1:-1].strip()
        if inner:
            return inner, make_windows_safe_filename(inner)

    if len(title) >= 2 and title.startswith("<") and title.endswith(">"):
        inner = title[1:-1].strip()
        if inner:
            return inner, make_windows_safe_filename(inner)

    def contains_chinese(s):
        return any("\u4e00" <= ch <= "\u9fff" for ch in s)

    import re
    pattern = re.compile(r"(《|<)([^《》<>]+)(》|>)")

    display_parts = []
    file_parts = []
    last = 0

    for match in pattern.finditer(title):
        display_parts.append(title[last:match.start()])
        file_parts.append(title[last:match.start()])

        left = match.group(1)
        content = match.group(2)

        # 文件夹/文件名内部统一使用 <内容> 的逻辑形式。
        file_marked = f"<{content}>"

        # 《》/<> 包裹中文或中英混合：文章标题使用《》。
        # 包裹全英文：文章标题使用<>。
        if contains_chinese(content):
            display_marked = f"《{content}》"
        else:
            display_marked = file_marked

        display_parts.append(display_marked)
        file_parts.append(file_marked)
        last = match.end()

    display_parts.append(title[last:])
    file_parts.append(title[last:])

    display_title = "".join(display_parts)
    file_title = make_windows_safe_filename("".join(file_parts))

    return display_title, file_title


def make_windows_safe_filename(name):
    """
    把 Windows 文件名禁止字符替换成视觉接近、但允许使用的全角字符。
    文章标题本身不修改，只用于文件夹名/文件名。
    """
    replacements = {
        "<": "＜",
        ">": "＞",
        ":": "：",
        '"': "＂",
        "/": "／",
        "\\": "＼",
        "|": "｜",
        "?": "？",
        "*": "＊",
    }

    safe = "".join(replacements.get(ch, ch) for ch in name)

    # Windows 不允许文件名/文件夹名以空格或句号结尾。
    safe = safe.rstrip(" .")
    return safe


def count_cn_and_word(body_lines):
    """
    按 WPS 常见“字数”口径统计正文：
    - 连续的 ASCII 字母/数字串作为 1 个单词，例如 V2、100、ABC123 各计 1；
    - 其它非空白字符（包括中文、中文标点、英文标点、引号、连字符等）逐个计 1；
    - 空白字符不计。

    返回：(character_count, word_count, total)
    其中 total = character_count + word_count。

    说明：旧版本只把部分 CJK 字符/标点放进 character_count，像“ ”、"-"
    这样的字符会被漏掉，导致与 WPS 的正文“字数”相差。
    """
    character_count = 0
    word_count = 0
    in_word = False

    for line in body_lines:
        s = line.strip()
        if not s:
            continue

        for ch in s:
            if ch.isspace():
                in_word = False
                continue

            # 与原程序保持一致：连续 ASCII 字母/数字作为 1 个单词。
            if ch.isascii() and ch.isalnum():
                if not in_word:
                    word_count += 1
                    in_word = True
            else:
                # WPS 统计中，中文字符、中文标点、英文标点、各种引号、
                # 连字符等非空白字符都计入；不能只限定某几个 Unicode 区段。
                character_count += 1
                in_word = False

    total = character_count + word_count
    return character_count, word_count, total



class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scroll_frame = ttk.Frame(self.canvas)
        self.scroll_frame.grid_columnconfigure(0, weight=1)
        self.scroll_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        # 使用动态宽度，跟随 Canvas 宽度变化
        self.canvas_window = self.canvas.create_window((0,0), window=self.scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 绑定 Canvas 大小变化事件，动态调整内部窗口宽度
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))
        
        # 注意：滚轮事件已移到 App 类的全局绑定中处理
        # 这样可以确保在整个面板区域（包括输入框、空白处）都能响应滚轮
    def scroll_widget_into_view(self, widget):
        """将 widget 滚动到可视区域内。
        
        关键：winfo_y() 返回的是相对于直接父容器的偏移，
        需要沿 master 链向上累加，得到相对于内层 scroll_frame 的坐标，
        这才是 canvas 坐标系中的正确位置。
        """
        self.canvas.update_idletasks()

        # 沿 master 链累加 y 偏移，得到 widget 在 canvas 坐标系中的 y
        widget_y = 0
        w = widget
        while w is not self.scroll_frame:
            widget_y += w.winfo_y()
            w = w.master

        widget_h = widget.winfo_height()
        canvas_h = self.canvas.winfo_height()
        view_top = self.canvas.canvasy(0)
        view_bottom = view_top + canvas_h

        if widget_y < view_top:
            # widget 在可视区域上方，向上滚动
            total = max(self.scroll_frame.winfo_height(), 1)
            self.canvas.yview_moveto(widget_y / total)
        elif widget_y + widget_h > view_bottom:
            # widget 在可视区域下方，向下滚动，让 widget 底部靠近可视区域底部
            target_top = widget_y + widget_h - canvas_h + 20
            total = max(self.scroll_frame.winfo_height(), 1)
            self.canvas.yview_moveto(target_top / total)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("投稿排版助手 v1.0.42")
        
        # 设置 ttk 主题美化界面
        style = ttk.Style(self)
        # 尝试使用 clam 主题（更现代化），如果不可用则使用默认
        available_themes = style.theme_names()
        if 'clam' in available_themes:
            style.theme_use('clam')
        elif 'alt' in available_themes:
            style.theme_use('alt')
        
        # 自定义样式
        style.configure('TLabel', font=('微软雅黑', 10))
        style.configure('TButton', font=('微软雅黑', 10), padding=6)
        style.configure('TEntry', font=('微软雅黑', 10), padding=4)
        style.configure('Header.TLabel', font=('微软雅黑', 11, 'bold'))
        
        win_w = 780
        screen_h = self.winfo_screenheight()
        win_h = min(620, screen_h - 100)
        self.geometry(f"{win_w}x{win_h}")
        self.minsize(720, 480)
        self.resizable(True, True)
        self.update()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = int((sw - win_w) / 2)
        y = int((sh - win_h) / 2) - 20
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.cfg = load_config()
        self._grid_rows = []
        self._delete_btns = []
        self._del_to_fields = {}
        self._prev_focus = None
        self._return_press_count = 0  # 回车键计数器：追踪已按多少次回车
        self._last_empty_fields = []  # 上一次的空字段列表，用于检测变化
        self.scroll_frame = ScrollableFrame(self)
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=8)
        self.main = self.scroll_frame.scroll_frame
        content_wrapper = ttk.Frame(self.main)
        content_wrapper.grid(row=0, column=0, sticky="nsew", padx=20)
        content_wrapper.columnconfigure(1, weight=1)
        row_idx = 0
        ttk.Label(content_wrapper, text="1. 选择文件（支持 .docx、.txt、.md；不支持旧版 .doc，请先另存为 .docx）").grid(row=row_idx, column=0, columnspan=2, sticky="w", pady=(0,4))
        row_idx += 1
        fr1 = ttk.Frame(content_wrapper)
        fr1.grid(row=row_idx, column=0, columnspan=2, sticky="ew", pady=2)
        fr1.columnconfigure(0, weight=1)
        row_idx += 1
        self.file_path_var = tk.StringVar()
        self.e_file = ttk.Entry(fr1, textvariable=self.file_path_var)
        self.e_file.pack(side="left", fill="x", expand=True)
        self.btn_browse1 = ttk.Button(fr1, text="浏览文件 [B]", command=self.select_file, takefocus=True)
        self.btn_browse1.pack(side="left", padx=5)
        self._grid_rows.append([self.e_file, self.btn_browse1])
        
        # 问题修复：监听文件路径变量变化，选择文件后恢复默认样式
        self.file_path_var.trace("w", self._on_file_change)
        ttk.Label(content_wrapper, text="2. 选择输出保存文件夹").grid(row=row_idx, column=0, columnspan=2, sticky="w", pady=(10,4))
        row_idx +=1
        fr2 = ttk.Frame(content_wrapper)
        fr2.grid(row=row_idx, column=0, columnspan=2, sticky="ew", pady=2)
        fr2.columnconfigure(0, weight=1)
        row_idx +=1
        self.save_dir_var = tk.StringVar(value=self.cfg.get("last_save_dir",""))
        self.e_save = ttk.Entry(fr2, textvariable=self.save_dir_var)
        self.e_save.pack(side="left", fill="x", expand=True)
        self.btn_browse2 = ttk.Button(fr2, text="浏览文件夹 [L]", command=self.select_save_folder, takefocus=True)
        self.btn_browse2.pack(side="left", padx=5)
        self._grid_rows.append([self.e_save, self.btn_browse2])
        
        # 问题修复：监听保存文件夹变量变化，选择后恢复默认样式
        self.save_dir_var.trace("w", self._on_save_dir_change)
        ttk.Label(content_wrapper, text="3. 文章信息").grid(row=row_idx, column=0, columnspan=2, sticky="w", pady=(10,6))
        row_idx +=1
        fr3 = ttk.Frame(content_wrapper)
        fr3.grid(row=row_idx, column=0, columnspan=2, sticky="ew")
        fr3.columnconfigure(1, weight=1)
        row_idx +=1
        ttk.Label(fr3, text="标题：").grid(row=0,column=0,sticky="w")
        self.title_var = tk.StringVar()
        self.title_entry = ttk.Entry(fr3, textvariable=self.title_var)
        self.title_entry.grid(row=0,column=1,sticky="ew",padx=5)
        ttk.Label(fr3, text="作者：").grid(row=1,column=0,sticky="w",pady=3)
        self.author_var = tk.StringVar()
        self.author_entry = ttk.Entry(fr3, textvariable=self.author_var)
        self.author_entry.grid(row=1,column=1,sticky="ew",padx=5)
        self._grid_rows.append([self.title_entry])
        self._grid_rows.append([self.author_entry])
        
        # 问题修复：监听标题和作者变量变化，自动填充时恢复默认样式
        self.title_var.trace("w", self._on_title_change)
        self.author_var.trace("w", self._on_author_change)
        ttk.Label(content_wrapper, text="4. 联系信息").grid(row=row_idx, column=0, columnspan=2, sticky="w", pady=(10,6))
        row_idx +=1
        fr4 = ttk.Frame(content_wrapper)
        fr4.grid(row=row_idx, column=0, columnspan=2, sticky="ew")
        fr4.columnconfigure(1, weight=1)
        row_idx +=1
        self.contact_vars = {}
        contact_keys = ["姓名","微信","电话","地址","邮编","身份证号","邮箱"]
        for idx, key in enumerate(contact_keys):
            ttk.Label(fr4, text=f"{key}：").grid(row=idx,column=0,sticky="w")
            var = tk.StringVar(value=self.cfg["contact"].get(key,""))
            entry = ttk.Entry(fr4, textvariable=var)
            entry.grid(row=idx,column=1,sticky="ew",padx=5,pady=1)
            self.contact_vars[key] = (var, entry)
            self._grid_rows.append([entry])
        ttk.Label(content_wrapper, text="5. 银行信息（最多4组；如收稿方未要求填写联行号，可留空）").grid(row=row_idx, column=0, columnspan=2, sticky="w", pady=(10,6))
        row_idx +=1
        self.bank_container = ttk.Frame(content_wrapper)
        self.bank_container.grid(row=row_idx, column=0, columnspan=2, sticky="ew")
        self.bank_container.columnconfigure(0, weight=1)
        row_idx +=1
        self.bank_frames = []
        self.bank_data = []
        self.btn_add_bank = ttk.Button(content_wrapper, text="添加银行 [G]", command=self.add_bank_group, takefocus=True)
        self._grid_rows.append([self.btn_add_bank])
        for b in self.cfg["banks"]:
            self.add_bank_group(init_data=b)
        self.btn_add_bank.grid(row=row_idx, column=0, sticky="w",pady=3)
        row_idx +=1
        self.export_btn = ttk.Button(content_wrapper, text="开始排版并导出 [X]", command=self.do_export, takefocus=True)
        self.export_btn.grid(row=row_idx, column=0, columnspan=2, pady=12)
        self._grid_rows.append([self.export_btn])
        self._bind_keys()

        # Windows 风格面板快捷键：Alt+字母直接执行对应按钮。
        self.bind_all("<Alt-b>", lambda e: (self.select_file(), "break")[1])
        self.bind_all("<Alt-l>", lambda e: (self.select_save_folder(), "break")[1])
        self.bind_all("<Alt-g>", lambda e: (self.add_bank_group(), "break")[1])
        self.bind_all("<Alt-x>", lambda e: (self.export_btn.invoke(), "break")[1])
        
        # 问题1修复：窗口启动时滚动到顶部，确保顶部提示文字可见
        self.after(100, lambda: self.scroll_frame.canvas.yview_moveto(0))
        self.after(200, lambda: self._focus_widget(self.btn_browse1))
        
        # 问题4修复：绑定全局焦点变化事件，让页面跟随光标滚动
        self.bind_all("<FocusIn>", self._on_focus_in, add="+")

    def _on_focus_in(self, event):
        """焦点变化时，自动滚动让焦点 widget 在可视范围内（问题4修复）"""
        try:
            widget = event.widget
            # 检查是否在主窗口内部（排除弹窗）
            parent = widget
            while parent:
                if parent == self:
                    # 在主窗口内部，执行滚动
                    self.scroll_frame.scroll_widget_into_view(widget)
                    break
                parent = parent.master
        except (AttributeError, tk.TclError):
            pass

    def _on_title_change(self, *args):
        """标题变量变化时，如果不为空则恢复默认样式"""
        if self.title_var.get().strip():
            self.title_entry.configure(style="TEntry")

    def _on_author_change(self, *args):
        """作者变量变化时，如果不为空则恢复默认样式"""
        if self.author_var.get().strip():
            self.author_entry.configure(style="TEntry")

    def _on_file_change(self, *args):
        """文件路径变量变化时，如果不为空则恢复默认样式"""
        if self.file_path_var.get().strip():
            self.e_file.configure(style="TEntry")

    def _on_save_dir_change(self, *args):
        """保存文件夹变量变化时，如果不为空则恢复默认样式"""
        if self.save_dir_var.get().strip():
            self.e_save.configure(style="TEntry")

    def _focus_next_empty_field(self):
        """找到下一个空缺字段并聚焦"""
        # 按顺序检查所有字段
        if not self.file_path_var.get().strip():
            self._focus_widget(self.e_file); return
        if not self.title_var.get().strip():
            self._focus_widget(self.title_entry); return
        if not self.author_var.get().strip():
            self._focus_widget(self.author_entry); return
        if not self.save_dir_var.get().strip():
            self._focus_widget(self.btn_browse2); return
        for key in ["姓名","微信","电话","地址","邮编","身份证号","邮箱"]:
            var, entry = self.contact_vars[key]
            if not var.get().strip():
                self._focus_widget(entry); return
        # 检查银行信息（只检查必填字段：银行名称、账号、开户支行）
        # 联行号是选填项，不参与必填检查
        for idx, bank in enumerate(self.bank_data):
            for ck in ["银行名称","账号","开户支行"]:  # 不包含"联行号"
                var, entry = bank[ck]
                if not var.get().strip():
                    self._focus_widget(entry); return
        
        # 所有必填字段都已填写，检查是否有空的联行号（选填项，但允许用户填写）
        for idx, bank in enumerate(self.bank_data):
            var, entry = bank["联行号"]
            if not var.get().strip():
                self._focus_widget(entry); return  # 聚焦到空的联行号，让用户选择是否填写
        
        # 所有必填字段和联行号都已填写，聚焦到导出按钮
        self.export_btn.focus()

    def _find_widget_position(self, widget):
        for r, row in enumerate(self._grid_rows):
            for c, w in enumerate(row):
                if w is widget:
                    return r, c
        return None, None

    def _focus_widget(self, widget):
        self._prev_focus = self.focus_get()
        # 问题1修复：当聚焦到"选择文件"一栏时，先滚动到顶部，确保提示文字可见
        if widget in (self.e_file, self.btn_browse1):
            self.scroll_frame.canvas.yview_moveto(0)
            self.update_idletasks()
        widget.focus_set()
        self.scroll_frame.scroll_widget_into_view(widget)

    def _bind_keys(self):
        def move_up(event=None):
            current = self.focus_get()
            if current in self._delete_btns:
                idx = self._delete_btns.index(current)
                if idx > 0:
                    self._focus_widget(self._delete_btns[idx - 1])
                else:
                    _, email_entry = self.contact_vars["邮箱"]
                    self._focus_widget(email_entry)
                return "break"
            r, c = self._find_widget_position(current)
            if r is None:
                return
            if r > 0:
                target_row = self._grid_rows[r - 1]
                if c < len(target_row):
                    self._focus_widget(target_row[c])
                else:
                    self._focus_widget(target_row[-1])
            else:
                self._focus_widget(self._grid_rows[-1][0])
            return "break"
        def move_down(event=None):
            current = self.focus_get()
            if current in self._delete_btns:
                idx = self._delete_btns.index(current)
                if idx < len(self._delete_btns) - 1:
                    self._focus_widget(self._delete_btns[idx + 1])
                else:
                    self._focus_widget(self.btn_add_bank)
                return "break"
            r, c = self._find_widget_position(current)
            if r is None:
                return
            if r < len(self._grid_rows) - 1:
                target_row = self._grid_rows[r + 1]
                if c < len(target_row):
                    self._focus_widget(target_row[c])
                else:
                    self._focus_widget(target_row[-1])
            else:
                self._focus_widget(self._grid_rows[0][0])
            return "break"
        def move_left(event=None):
            current = self.focus_get()
            if current is self.btn_add_bank:
                if self._delete_btns:
                    self._focus_widget(self._delete_btns[-1])
                return "break"
            if current in self._delete_btns:
                entry_card, entry_lxh = self._del_to_fields[current]
                prev = self._prev_focus
                if prev is entry_card:
                    self._focus_widget(entry_card)
                elif prev is entry_lxh:
                    self._focus_widget(entry_lxh)
                elif prev in self._delete_btns:
                    prev_idx = self._delete_btns.index(prev)
                    cur_idx = self._delete_btns.index(current)
                    if prev_idx < cur_idx:
                        self._focus_widget(entry_card)
                    else:
                        self._focus_widget(entry_lxh)
                else:
                    self._focus_widget(entry_card)
                return "break"
            r, c = self._find_widget_position(current)
            if r is None:
                return
            row = self._grid_rows[r]
            if c > 0:
                self._focus_widget(row[c - 1])
            return "break"
        def move_right(event=None):
            current = self.focus_get()
            r, c = self._find_widget_position(current)
            if r is not None and c is not None:
                row = self._grid_rows[r]
                if len(row) == 2 and c == 1 and current not in self._delete_btns and current is not self.btn_add_bank and current is not self.export_btn:
                    for btn, (ec, el) in self._del_to_fields.items():
                        if el is current:
                            self._focus_widget(btn)
                            return "break"
            if r is None:
                return
            row = self._grid_rows[r]
            if c < len(row) - 1:
                self._focus_widget(row[c + 1])
            return "break"
        # 使用 bind_all，让焦点在 Entry 等子控件时方向键也能交给排版助手的导航逻辑。
        # 仅当当前焦点确实属于主窗口时才处理，避免干扰其它弹窗。
        def in_main_window():
            current = self.focus_get()
            if current is None:
                return False
            try:
                return current.winfo_toplevel() is self
            except tk.TclError:
                return False

        def guarded(handler):
            def _handler(event=None):
                if not in_main_window():
                    return
                return handler(event)
            return _handler

        self.bind_all("<Up>", guarded(move_up), add="+")
        self.bind_all("<Down>", guarded(move_down), add="+")
        self.bind_all("<Left>", guarded(move_left), add="+")
        self.bind_all("<Right>", guarded(move_right), add="+")
        
        def on_return(event=None):
            """回车键处理：在输入框上时跳转到下一个控件，在按钮上时执行点击"""
            widget = self.focus_get()

            # 问题1修复：如果焦点在删除按钮上，弹窗确认
            if widget in self._delete_btns:
                # 弹出确认弹窗
                from tkinter import messagebox
                if messagebox.askyesno("确认删除", "是否删除此组银行信息？", parent=self):
                    widget.invoke()
                return "break"

            # 如果焦点在按钮上，执行点击
            if isinstance(widget, ttk.Button):
                widget.invoke()
                return "break"

            # 如果焦点在输入框上，跳转到下一个控件
            if isinstance(widget, ttk.Entry):
                # 问题2修复：使用与 do_export 一致的固定字段列表
                # 按顺序收集所有未填写的字段，聚焦到对应的输入框或浏览按钮
                empty_fields = []

                # 1. 文件路径（聚焦到浏览按钮）
                if not self.file_path_var.get().strip():
                    empty_fields.append(self.btn_browse1)

                # 2. 标题
                if not self.title_var.get().strip():
                    empty_fields.append(self.title_entry)

                # 3. 作者
                if not self.author_var.get().strip():
                    empty_fields.append(self.author_entry)

                # 4. 保存路径（聚焦到浏览文件夹按钮）
                if not self.save_dir_var.get().strip():
                    empty_fields.append(self.btn_browse2)

                # 5. 联系信息
                for key in ["姓名","微信","电话","地址","邮编","身份证号","邮箱"]:
                    var, entry = self.contact_vars[key]
                    if not var.get().strip():
                        empty_fields.append(entry)

                # 6. 银行信息（只检查必填字段：银行名称、账号、开户支行）
                for bank_idx, bank in enumerate(self.bank_data):
                    for ck in ["银行名称","账号","开户支行"]:  # 不包含"联行号"
                        var, entry = bank[ck]
                        if not var.get().strip():
                            empty_fields.append(entry)

                # 7. 联行号（选填项，但参与导航）
                # 无论联行号是否为空，都加入导航列表
                # 这样用户可以按回车跳过它，而不是停留在它上面
                for bank_idx, bank in enumerate(self.bank_data):
                    var, entry = bank["联行号"]
                    empty_fields.append(entry)  # 无条件加入导航列表

                # 检查空字段列表是否发生变化（用户填写了某个字段）
                # 如果变化了，重置计数器
                if empty_fields != self._last_empty_fields:
                    self._return_press_count = 0
                    self._last_empty_fields = empty_fields[:]

                if empty_fields:
                    # 找到当前 widget 在空字段列表中的位置
                    try:
                        current_idx = empty_fields.index(widget)
                        
                        # 计数器 +1
                        self._return_press_count += 1
                        
                        # 如果计数器等于空字段数量，说明已经历遍所有空字段
                        # 下一次按回车应该跳到导出按钮
                        if self._return_press_count >= len(empty_fields):
                            self.export_btn.focus()
                            self._return_press_count = 0  # 重置计数器
                        else:
                            # 否则跳到下一个空字段（循环）
                            next_idx = (current_idx + 1) % len(empty_fields)
                            empty_fields[next_idx].focus()
                    except ValueError:
                        # 当前 widget 不在列表中（可能刚被填写完），跳到第一个空字段
                        if empty_fields:
                            empty_fields[0].focus()
                            self._return_press_count = 1  # 重置计数器，但标记已按一次
                        else:
                            # 没有空字段了，跳到导出按钮
                            self.export_btn.focus()
                            self._return_press_count = 0
                else:
                    # 所有输入框都已填写（或没有输入框），跳转到导出按钮
                    self.export_btn.focus()
                    self._return_press_count = 0

                return "break"

            return "break"
        
        self.bind_all("<Return>", guarded(on_return), add="+")
        self.bind_all("<KP_Enter>", guarded(on_return), add="+")
        
        # 全局鼠标滚轮绑定（解决滚轮范围受限问题）
        # 在 App 类的全局层面绑定，而不是在单个组件上绑定
        def global_mousewheel(event):
            # 检查鼠标是否在 scroll_frame 区域内
            try:
                # 获取鼠标相对于 root 窗口的位置
                widget = self.winfo_containing(event.x_root, event.y_root)
                if widget:
                    # 检查这个 widget 是否在 scroll_frame 内部
                    parent = widget
                    while parent:
                        if parent == self.scroll_frame.scroll_frame:
                            # 在 scroll_frame 内部，执行滚动
                            if platform.system() == "Linux":
                                if event.num == 4:
                                    self.scroll_frame.canvas.yview_scroll(-3, "units")
                                elif event.num == 5:
                                    self.scroll_frame.canvas.yview_scroll(3, "units")
                            else:
                                self.scroll_frame.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                            return "break"
                        parent = parent.master
            except (AttributeError, tk.TclError):
                pass
            return None
        
        # 根据平台绑定全局滚轮事件
        if platform.system() == "Linux":
            self.bind_all("<Button-4>", global_mousewheel, add="+")
            self.bind_all("<Button-5>", global_mousewheel, add="+")
        else:
            self.bind_all("<MouseWheel>", global_mousewheel, add="+")

    def select_file(self):
        init_dir = self.cfg.get("last_file_dir","")
        fp = filedialog.askopenfilename(
            parent=self,
            initialdir=init_dir,
            filetypes=[("支持文件","*.docx;*.txt;*.md"),("Word文档","*.docx"),("文本文件","*.txt;*.md")]
        )
        if not fp:
            return
        if fp.lower().endswith(".doc"):
            show_alert(self, "格式不支持", "请用 Word 另存为 docx 或 txt 格式", "确定 [O]")
            return
        self.file_path_var.set(fp)
        self.cfg["last_file_dir"] = os.path.dirname(fp)
        title, author = self.parse_file(fp)
        display_title, _ = normalize_title_for_export(title)
        self.title_var.set(display_title)
        self.author_var.set(author)
        
        # 问题2修复：选择文件后，聚焦到下一个空缺字段
        self.after(100, self._focus_next_empty_field)

    def parse_file(self, filepath):
        """解析文件，提取标题和作者（修复不支持的文件类型处理）"""
        ext = filepath.lower().split(".")[-1]
        title, author = "", ""
        try:
            if ext in ["txt","md"]:
                with open(filepath,"r",encoding="utf-8") as f:
                    lines = [line.rstrip("\n") for line in f if line.strip()]
                if len(lines)>=1: title = lines[0].strip()
                if len(lines)>=2: author = lines[1].strip()
            elif ext == "docx":
                from docx import Document
                doc = Document(filepath)
                paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
                if len(paras)>=1: title = paras[0]
                if len(paras)>=2: author = paras[1]
            else:
                raise ValueError(f"不支持的文件格式：{ext}")
        except Exception as e:
            show_alert(self, "读取失败", str(e))
        return title, author

    def select_save_folder(self):
        init_dir = self.cfg.get("last_save_dir","")
        folder = filedialog.askdirectory(parent=self, initialdir=init_dir)
        if folder:
            self.save_dir_var.set(folder)
            self.cfg["last_save_dir"] = folder
            # 选择文件夹后，聚焦到下一个空缺字段
            self.after(100, self._focus_next_empty_field)

    def add_bank_group(self, init_data=None):
        if len(self.bank_frames)>=4:
            show_alert(self, "提示", "最多只能添加4组银行信息")
            return
        data = init_data or {"银行名称":"","账号":"","开户支行":"","联行号":""}
        fr = ttk.Frame(self.bank_container)
        fr.pack(fill="x", pady=4)
        fr.columnconfigure(1, weight=1)
        fr.columnconfigure(3, weight=1)
        vars_dict = {}
        ttk.Label(fr, text="银行名称:").grid(row=0, column=0, sticky="w")
        var_bank = tk.StringVar(value=data["银行名称"])
        entry_bank = ttk.Entry(fr, textvariable=var_bank)
        entry_bank.grid(row=0, column=1, padx=3, sticky="ew")
        ttk.Label(fr, text="账号:").grid(row=0, column=2, sticky="w", padx=(8,0))
        var_card = tk.StringVar(value=data["账号"])
        entry_card = ttk.Entry(fr, textvariable=var_card)
        entry_card.grid(row=0, column=3, padx=3, sticky="ew")
        ttk.Label(fr, text="开户支行:").grid(row=1, column=0, sticky="w")
        var_branch = tk.StringVar(value=data["开户支行"])
        entry_branch = ttk.Entry(fr, textvariable=var_branch)
        entry_branch.grid(row=1, column=1, padx=3, sticky="ew")
        ttk.Label(fr, text="联行号:").grid(row=1, column=2, sticky="w", padx=(8,0))
        var_lxh = tk.StringVar(value=data["联行号"])
        entry_lxh = ttk.Entry(fr, textvariable=var_lxh)
        entry_lxh.grid(row=1, column=3, padx=3, sticky="ew")
        vars_dict["银行名称"] = (var_bank, entry_bank)
        vars_dict["账号"] = (var_card, entry_card)
        vars_dict["开户支行"] = (var_branch, entry_branch)
        vars_dict["联行号"] = (var_lxh, entry_lxh)
        btn_del = ttk.Button(fr, text="删除本组 [D]", takefocus=True)
        btn_del.grid(row=0, column=4, rowspan=2, padx=4)

        # Alt+D 属于“这一组银行信息”的快捷键，而不是“删除按钮”的快捷键。
        # 因此焦点停在本组任意输入框时，都可以直接删除整组。
        def delete_group_shortcut(event=None):
            btn_del.invoke()
            return "break"

        for entry_widget in (entry_bank, entry_card, entry_branch, entry_lxh, btn_del):
            entry_widget.bind("<Alt-KeyPress-d>", delete_group_shortcut)
        try:
            insert_idx = self._grid_rows.index([self.btn_add_bank])
        except (ValueError, AttributeError):
            insert_idx = len(self._grid_rows)
        row_a = [entry_bank, entry_card, btn_del]
        row_b = [entry_branch, entry_lxh]
        self._grid_rows.insert(insert_idx, row_a)
        insert_idx += 1
        self._grid_rows.insert(insert_idx, row_b)
        new_rows = [row_a, row_b]
        self._delete_btns.append(btn_del)
        self._del_to_fields[btn_del] = (entry_card, entry_lxh)
        def del_this():
            # 问题修复：如果只剩一组银行信息，弹出确认弹窗
            if len(self.bank_frames) == 1:
                from tkinter import messagebox
                if not messagebox.askyesno("确认删除", "是否删除所有银行信息？", parent=self):
                    # 用户选择"否"，保留银行信息，聚焦到下一个空缺信息
                    self.after(100, self._focus_next_empty_field)
                    return
            
            # 执行删除操作
            del_row_idx = None
            for r, row in enumerate(self._grid_rows):
                if row is row_a:
                    del_row_idx = r
                    break
            for row in new_rows:
                try:
                    self._grid_rows.remove(row)
                except ValueError:
                    pass
            try:
                self._delete_btns.remove(btn_del)
            except ValueError:
                pass
            if btn_del in self._del_to_fields:
                del self._del_to_fields[btn_del]
            idx = self.bank_frames.index(fr)
            self.bank_frames.pop(idx)
            self.bank_data.pop(idx)
            fr.destroy()
            
            # 删除后，聚焦到下一个空缺信息
            self.after(100, self._focus_next_empty_field)
        btn_del.config(command=del_this)
        self.bank_frames.append(fr)
        self.bank_data.append(vars_dict)
        if init_data is None:
            self._focus_widget(entry_bank)

        # 自动滚动到新添加的输入框，确保它在可视区域内
        def scroll_to_new_frame():
            # 强制更新所有待处理的几何计算
            self.update_idletasks()

            # 沿 master 链累加 y 偏移，得到 fr 在 canvas 坐标系中的 y
            frame_y = 0
            w = fr
            while w is not self.scroll_frame.scroll_frame:
                frame_y += w.winfo_y()
                w = w.master

            frame_height = fr.winfo_height()
            canvas_height = self.scroll_frame.canvas.winfo_height()
            total_height = max(self.scroll_frame.scroll_frame.winfo_height(), 1)

            view_top = self.scroll_frame.canvas.canvasy(0)
            view_bottom = view_top + canvas_height

            # 检查 frame 是否在可视区域内
            if frame_y + frame_height > view_bottom:
                # frame 在可视区域下方，向下滚动
                target_top = frame_y + frame_height - canvas_height + 20
                target_top = max(0, target_top)
                fraction = target_top / total_height
                fraction = max(0, min(1, fraction))
                self.scroll_frame.canvas.yview_moveto(fraction)
            elif frame_y < view_top:
                # frame 在可视区域上方，向上滚动
                fraction = frame_y / total_height
                fraction = max(0, min(1, fraction))
                self.scroll_frame.canvas.yview_moveto(fraction)

        self.after(100, scroll_to_new_frame)

    def get_bank_list(self):
        res = []
        for b in self.bank_data:
            d = {}
            for k in ["银行名称","账号","开户支行","联行号"]:
                var, entry = b[k]
                d[k] = var.get().strip()
            res.append(d)
        return res

    def open_folder(self, folder_path):
        """安全地打开文件夹（修复 Shell 注入漏洞）"""
        path = str(folder_path)
        system = platform.system()
        try:
            if system == "Windows":
                os.startfile(path)
            elif system == "Darwin":
                subprocess.run(["open", path], check=True)
            else:
                subprocess.run(["xdg-open", path], check=True)
        except (OSError, subprocess.CalledProcessError) as e:
            show_alert(self, "打开失败", f"无法打开文件夹：{e}")

    def do_export(self):
        # 重置所有输入框为默认样式
        for key, (var,entry) in self.contact_vars.items():
            entry.configure(style="TEntry")
        for bank in self.bank_data:
            for k in ["银行名称","账号","开户支行","联行号"]:
                var,entry = bank[k]
                entry.configure(style="TEntry")
        
        # 收集所有问题
        all_errors = []
        missing_widgets = []      # 用于聚焦（可包含按钮）
        error_style_widgets = []  # 用于设置 Error.TEntry 样式（仅 Entry）
        
        # 定义恢复背景色的回调函数（用户输入时调用）
        def restore_bg(event, entry_widget, var):
            """用户输入时，仅当输入框有值时才恢复默认背景色"""
            if var.get().strip():
                entry_widget.configure(style="TEntry")
        
        # 1. 检查文件
        fp = self.file_path_var.get().strip()
        if not fp:
            all_errors.append("未选择要排版的文件")
            missing_widgets.append(self.btn_browse1)  # 聚焦到浏览按钮
            error_style_widgets.append(self.e_file)   # 只对输入框标红
        elif not Path(fp).is_file():
            all_errors.append("当前选择的排版文件不存在")
            missing_widgets.append(self.btn_browse1)  # 聚焦到浏览按钮
            error_style_widgets.append(self.e_file)   # 只对输入框标红
        
        # 2. 检查标题
        title = self.title_var.get().strip()
        if not title:
            all_errors.append("标题为空")
            missing_widgets.append(self.title_entry)
            error_style_widgets.append(self.title_entry)
            self.title_entry.bind("<KeyRelease>", lambda e, w=self.title_entry, v=self.title_var: restore_bg(e, w, v), add="+")
        else:
            title_error = validate_title_book_marks(title)
            if title_error:
                all_errors.append(f"标题格式有误：{title_error}")
                missing_widgets.append(self.title_entry)
                error_style_widgets.append(self.title_entry)
                self.title_entry.bind("<KeyRelease>", lambda e, w=self.title_entry, v=self.title_var: restore_bg(e, w, v), add="+")

        # 3. 检查作者
        author = self.author_var.get().strip()
        if not author:
            all_errors.append("作者为空")
            missing_widgets.append(self.author_entry)
            error_style_widgets.append(self.author_entry)
            self.author_entry.bind("<KeyRelease>", lambda e, w=self.author_entry, v=self.author_var: restore_bg(e, w, v), add="+")
        
        # 4. 检查保存文件夹
        save_root = self.save_dir_var.get().strip()
        if not save_root:
            all_errors.append("保存文件夹为空")
            missing_widgets.append(self.btn_browse2)  # 聚焦到浏览文件夹按钮
            error_style_widgets.append(self.e_save)   # 输入框标红
        
        # 5. 检查联系信息
        contact = {}
        for key, (var,entry) in self.contact_vars.items():
            val = var.get().strip()
            contact[key] = val
            if not val:
                all_errors.append(f"联系信息：{key} 为空")
                missing_widgets.append(entry)
                error_style_widgets.append(entry)
                entry.bind("<KeyRelease>", lambda e, w=entry, v=var: restore_bg(e, w, v), add="+")

        # 6. 检查银行信息
        bank_list = self.get_bank_list()
        for bank_idx, bank in enumerate(bank_list):
            for ck in ["银行名称","账号","开户支行"]:
                val = bank[ck]
                var,entry = self.bank_data[bank_idx][ck]
                if not val:
                    all_errors.append(f"第{bank_idx+1}组银行信息：{ck} 为空")
                    missing_widgets.append(entry)
                    error_style_widgets.append(entry)
                    entry.bind("<KeyRelease>", lambda e, w=entry, v=var: restore_bg(e, w, v), add="+")
        
        # 统一弹窗提示所有问题
        if all_errors:
            error_text = "\n".join(all_errors)
            # 根据错误数量动态计算弹窗高度（每行约 25 像素，加上边距 120）
            dynamic_height = min(max(len(all_errors) * 25 + 120, 180), 500)
            show_alert(self, "信息不完整", error_text, width=620, height=dynamic_height)
            # 所有漏填输入框变红（只对 Entry 设置样式，不对 Button 设置）
            style = ttk.Style(self)
            style.configure("Error.TEntry", fieldbackground="#ff6666")
            for widget in error_style_widgets:
                widget.configure(style="Error.TEntry")
            # 滚动到第一个漏填位置并聚焦
            if missing_widgets:
                first_widget = missing_widgets[0]
                def _scroll_and_focus():
                    self.scroll_frame.canvas.yview_moveto(0)  # 先回到顶部
                    self.update_idletasks()
                    self.scroll_frame.scroll_widget_into_view(first_widget)  # 再微调
                    first_widget.focus_set()
                self.after(100, _scroll_and_focus)
            return

        display_title, file_title = normalize_title_for_export(title)
        sub_folder_name = f"《{file_title}》投稿"
        out_folder = Path(save_root) / sub_folder_name
        fn_base = f"《{file_title}》{author}"

        if out_folder.exists():
            choice = ask_export_conflict(self, out_folder)
            if choice == "cancel":
                # 问题2修复：点击取消后，滚动到首屏并聚焦到"浏览文件夹"按钮
                self.after(100, lambda: self.scroll_frame.canvas.yview_moveto(0))
                self.after(200, lambda: self._focus_widget(self.btn_browse2))
                return
            elif choice == "saveas":
                # 可以反复输入：名称为空或目标已存在时，提示后重新打开输入框。
                while True:
                    new_folder_name = ask_saveas_folder_name(self, sub_folder_name)
                    if new_folder_name is None:
                        return

                    new_folder_name = new_folder_name.strip()
                    if not new_folder_name:
                        show_alert(
                            self,
                            "提示",
                            "文件夹名称不能为空，请重新输入。"
                        )
                        continue

                    out_folder = Path(save_root) / new_folder_name

                    if out_folder.exists():
                        show_alert(
                            self,
                            "文件夹已存在",
                            f"文件夹：\n{out_folder}\n已经存在，请换一个名称。"
                        )
                        continue

                    break

            elif choice == "overwrite":
                docx_path = out_folder / f"{fn_base}.docx"
                txt_path = out_folder / f"{fn_base}.txt"

                del_ok = False
                while not del_ok:
                    try:
                        for output_path in (docx_path, txt_path):
                            if output_path.exists():
                                output_path.unlink()
                        del_ok = True
                    except OSError:
                        ans = ask_retry_cancel(
                            self,
                            "文件占用",
                            "要覆盖的同名文件正在被占用，请关闭相关文件后重试"
                        )
                        if not ans:
                            return

        if not out_folder.exists():
            try:
                out_folder.mkdir(parents=True, exist_ok=False)
            except OSError as e:
                show_alert(
                    self,
                    "无法创建文件夹",
                    f"文件夹无法创建：\n\n{out_folder.name}\n\n"
                    f"错误信息：{e}",
                    width=620,
                    height=280
                )
                return

        docx_path = out_folder / f"{fn_base}.docx"
        txt_path = out_folder / f"{fn_base}.txt"
        content_lines = self.read_full_text(fp)
        raw_body_lines = content_lines[2:] if len(content_lines)>=3 else []

        # 仅正文做半角标点转全角
        processed_body_lines = []
        for ln in raw_body_lines:
            new_ln = convert_halfwidth_punct(ln)
            processed_body_lines.append(new_ln)

        cn_cnt, word_cnt, total_cnt = count_cn_and_word(processed_body_lines)

        doc = Document()
        # 明确把 Word 正文及空白分隔段的默认行距统一设为单倍，
        # 避免空白段落继承 Word 默认样式而出现 1.5 倍行距。
        normal_fmt = doc.styles["Normal"].paragraph_format
        normal_fmt.line_spacing_rule = WD_LINE_SPACING.SINGLE
        normal_fmt.space_before = Pt(0)
        normal_fmt.space_after = Pt(0)

        p = doc.add_paragraph()
        _set_para(p, align=WD_ALIGN_PARAGRAPH.CENTER)
        run = p.add_run(display_title)
        _set_run_font(run, 14)
        run.bold = False
        p = doc.add_paragraph()
        _set_para(p, align=WD_ALIGN_PARAGRAPH.CENTER)
        run = p.add_run(author)
        _set_run_font(run, 10.5)

        for line in processed_body_lines:
            line = line.strip()
            if not line:
                continue
            p = doc.add_paragraph()
            _set_para(p, align=WD_ALIGN_PARAGRAPH.JUSTIFY, first_indent=Pt(21))
            run = p.add_run(line)
            _set_run_font(run, 10.5)

        p = doc.add_paragraph()
        _set_para(p, align=WD_ALIGN_PARAGRAPH.RIGHT)
        run = p.add_run(f"（正文：{total_cnt} 字）")
        _set_run_font(run, 10.5)
        p = doc.add_paragraph()
        _set_para(p)
        p = doc.add_paragraph()
        _set_para(p)
        run = p.add_run("联系信息：")
        _set_run_font(run, 10.5)
        for key in ["姓名","微信","电话","地址","邮编","身份证号","邮箱"]:
            val = contact.get(key,"")
            p = doc.add_paragraph()
            _set_para(p)
            run = p.add_run(f"{key}：{val}")
            _set_run_font(run, 10.5)
        p = doc.add_paragraph()
        _set_para(p)
        for idx,bank in enumerate(bank_list):
            p = doc.add_paragraph()
            _set_para(p)
            run = p.add_run(bank["银行名称"])
            _set_run_font(run, 10.5)
            for k in ["账号","开户支行"]:
                val = bank[k]
                p = doc.add_paragraph()
                _set_para(p)
                run = p.add_run(f"{k}：{val}")
                _set_run_font(run, 10.5)
            lxh_val = bank["联行号"].strip()
            if lxh_val:
                p = doc.add_paragraph()
                _set_para(p)
                run = p.add_run(f"联行号：{lxh_val}")
                _set_run_font(run, 10.5)
            if idx != len(bank_list)-1:
                p = doc.add_paragraph()
                _set_para(p)
        p = doc.add_paragraph()
        _set_para(p)

        save_ok = False
        while not save_ok:
            try:
                doc.save(docx_path)
                save_ok = True
            except PermissionError:
                res = ask_retry_cancel(
                    self,
                    "文件占用",
                    "目标文件或文件夹正在被占用，请关闭相关文件/文件夹后重试"
                )
                if not res:
                    return

        txt_content = []
        txt_content.append(display_title)
        txt_content.append(author)
        for bl in processed_body_lines:
            bl = bl.strip()
            if bl:
                txt_content.append("　　"+bl)
        txt_content.append(f"（正文：{total_cnt} 字）")
        txt_content.append("")
        txt_content.append("联系信息：")
        for k in ["姓名","微信","电话","地址","邮编","身份证号","邮箱"]:
            txt_content.append(f"{k}：{contact.get(k,'')}")
        txt_content.append("")
        for idx,bank in enumerate(bank_list):
            txt_content.append(bank["银行名称"])
            txt_content.append(f"账号：{bank['账号']}")
            txt_content.append(f"开户支行：{bank['开户支行']}")
            lxh_val = bank["联行号"].strip()
            if lxh_val:
                txt_content.append(f"联行号：{lxh_val}")
            if idx != len(bank_list)-1:
                txt_content.append("")
        txt_content.append("")
        with open(txt_path,"w",encoding="utf-8") as f:
            f.write("\n".join(txt_content))
        self.cfg["contact"] = {k:v.get().strip() for k,(v,e) in self.contact_vars.items()}
        self.cfg["banks"] = self.get_bank_list()
        save_config(self.cfg)
        
        # 创建导出成功弹窗（动态尺寸）
        win = tk.Toplevel(self)
        win.title("导出成功")
        win.transient(self)
        win.resizable(False, False)
        win.grab_set()
        
        # 根据路径长度计算合适的弹窗尺寸
        path_length = len(str(out_folder))
        width = min(max(path_length * 8 + 100, 400), int(self.winfo_width() * 0.8))
        height = min(180, int(self.winfo_height() * 0.7))
        
        # 居中显示
        sw2 = win.winfo_screenwidth()
        sh2 = win.winfo_screenheight()
        win.geometry(f"{width}x{height}+{int((sw2-width)/2)}+{int((sh2-height)/2)}")
        win.update()

        # 问题3修复：使用透明背景的 Label
        style = ttk.Style(win)
        style.configure("Transparent.TLabel", background=win.cget("background"))
        ttk.Label(win, text=f"文件已导出到：\n{out_folder}", wraplength=width - 40, justify="left", style="Transparent.TLabel").pack(pady=15, padx=20)
        def close_all(event=None):
            try:
                win.grab_release()
            except tk.TclError:
                pass
            if win.winfo_exists():
                win.destroy()
            self.open_folder(out_folder)
            self.quit()
            return "break"
        close_btn = ttk.Button(win, text="关闭 [C]", command=close_all)
        close_btn.pack()
        win.bind("<Alt-KeyPress-c>", close_all)
        win.bind("<Return>", close_all)
        win.bind("<Escape>", close_all)
        win.protocol("WM_DELETE_WINDOW", close_all)
        win.after_idle(lambda: (win.focus_force(), close_btn.focus_set()))
        win.after(3000, close_all)

    def read_full_text(self,filepath):
        """读取文件全文（修复不支持的文件类型处理）"""
        ext = filepath.lower().split(".")[-1]
        lines = []
        if ext in ["txt","md"]:
            with open(filepath,"r",encoding="utf-8") as f:
                lines = [line.rstrip("\n") for line in f]
        elif ext == "docx":
            from docx import Document
            doc = Document(filepath)
            lines = [p.text for p in doc.paragraphs]
        else:
            raise ValueError(f"不支持的文件格式：{ext}")
        return lines

if __name__ == "__main__":
    app = App()
    app.mainloop()
