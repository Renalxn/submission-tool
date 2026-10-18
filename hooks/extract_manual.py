# -*- coding: utf-8 -*-
"""
运行时钩子：释放用户手册到 exe 同级目录
"""
import sys
import os

def extract_user_manual():
    """释放用户手册到 exe 同级目录"""
    try:
        # 获取 exe 所在目录
        if getattr(sys, 'frozen', False):
            # 打包后的 exe
            exe_dir = os.path.dirname(sys.executable)
        else:
            # 开发环境
            exe_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 用户手册在打包时的路径
        manual_source = os.path.join(sys._MEIPASS, 'docs', '用户手册.txt')
        manual_target = os.path.join(exe_dir, '用户手册.txt')
        
        # 如果用户手册不存在，则释放
        if os.path.exists(manual_source) and not os.path.exists(manual_target):
            with open(manual_source, 'rb') as f_in:
                with open(manual_target, 'wb') as f_out:
                    f_out.write(f_in.read())
    except Exception:
        pass  # 静默失败，不影响程序运行

# 执行释放
extract_user_manual()
