# 投稿排版工具 v1.0.35 Bug 修复分析报告

**日期：** 2026-10-17  
**分析模型：** Qwen3.8 Max  
**修复版本：** v1.0.35+

---

## 📋 问题总结

本次修复了两个关键问题：

1. **浏览按钮样式异常**（反复出现）：按钮变长、文字消失、红色不消失
2. **选择文件夹后光标未移动**：用户选择保存文件夹后，光标没有自动跳转到下一个必填字段

---

## 🔍 问题 1：浏览按钮样式异常

### 现象描述

- 用户未选择文件，关闭提示弹窗后：
  - "浏览文件"按钮**变长**、**文字消失**
  - 用户选择文件后，按钮的**红色没有消失**，**大小和文字没有恢复**

### 历史修复记录

| 版本 | 聚焦目标 | 结果 | 原因 |
|------|---------|------|------|
| v1.0.32 | btn_browse1 | ❌ 失败 | 按钮被设置 Error.TEntry 样式 |
| v1.0.33 | e_file | ✅ 成功 | 按钮不在 missing_widgets 中 |
| v1.0.34 | btn_browse1 | ❌ 失败 | 按钮又被设置 Error.TEntry 样式 |

### 根本原因

**真正的 bug 不在"聚焦到谁"，而在第 1417-1419 行的样式设置循环：**

```python
# 第 1417-1419 行（修复前）
style.configure("Error.TEntry", fieldbackground="#ff6666")
for widget in missing_widgets:
    widget.configure(style="Error.TEntry")   # ← BUG：对按钮也执行了！
```

**问题分析：**

1. `missing_widgets` 列表包含：
   - `btn_browse1`（浏览文件按钮，第 1353 行）
   - `btn_browse2`（浏览文件夹按钮，第 1384 行）
   - 各种 Entry 输入框

2. `Error.TEntry` 是专门为 `ttk.Entry` 设计的样式，包含：
   - `fieldbackground` 属性（控制输入框背景色）
   - 特定的 padding、border 布局

3. **当把 Entry 样式强加给 Button 时：**
   - ttk 引擎找不到 Button 对应的布局元素（Button 没有 `fieldbackground` 属性映射）
   - 导致按钮文字消失、尺寸异常（变长）
   - 红色不消失是因为 `_on_file_change`（第 869 行）只恢复 `e_file` 的样式，不恢复按钮的样式

### 为什么 v1.0.34 又失败了？

**完整因果链：**

```
v1.0.32:
  missing_widgets = [btn_browse1, ...]
  ↓
  循环设置 Error.TEntry
  ↓
  btn_browse1.configure(style="Error.TEntry")  ← 按钮样式损坏
  ↓
  ❌ 失败

v1.0.33:
  missing_widgets = [e_file, ...]  ← 改为聚焦到输入框
  ↓
  循环设置 Error.TEntry
  ↓
  e_file.configure(style="Error.TEntry")  ← 只有输入框被设置
  ↓
  ✅ 成功（按钮没被触碰）

v1.0.34:
  missing_widgets = [btn_browse1, ...]  ← 又改回聚焦到按钮
  ↓
  循环设置 Error.TEntry
  ↓
  btn_browse1.configure(style="Error.TEntry")  ← 按钮样式又损坏
  ↓
  ❌ 失败
```

**核心问题：** 无论聚焦到谁，只要按钮出现在 `missing_widgets` 里，它就会被 `Error.TEntry` 毁掉。

### 额外问题

**第 1386 行的 command 覆盖：**

```python
self.btn_browse2.configure(command=lambda: (self.select_save_folder(), self.e_save.configure(style="TEntry")))
```

这行代码：
- 覆盖了 `btn_browse2` 的原始 command
- 虽然 lambda 中只对 `e_save` 设置样式（不直接伤害按钮）
- 但这种写法脆弱且不必要，因为 `_on_save_dir_change`（第 873 行）已经通过 `trace` 自动处理了样式恢复

---

## 🔧 修复方案 1

### 核心思路

**分离"聚焦列表"和"样式列表"：**

- `missing_widgets`：用于聚焦（可包含按钮）
- `error_style_widgets`：用于设置 Error.TEntry 样式（仅 Entry）

### 具体改动

**1. 新增 `error_style_widgets` 列表（第 1342 行）：**

```python
# 收集所有问题
all_errors = []
missing_widgets = []      # 用于聚焦（可包含按钮）
error_style_widgets = []  # 用于设置 Error.TEntry 样式（仅 Entry）
```

**2. 每个检查分支中，分别添加到对应列表：**

```python
# 1. 检查文件
if not fp:
    all_errors.append("未选择要排版的文件")
    missing_widgets.append(self.btn_browse1)  # 聚焦到浏览按钮
    error_style_widgets.append(self.e_file)   # 只对输入框标红
```

**3. 样式设置循环改为只遍历 `error_style_widgets`（第 1420 行）：**

```python
# 所有漏填输入框变红（只对 Entry 设置样式，不对 Button 设置）
style = ttk.Style(self)
style.configure("Error.TEntry", fieldbackground="#ff6666")
for widget in error_style_widgets:
    widget.configure(style="Error.TEntry")
```

**4. 删除第 1386 行的 command 覆盖：**

```python
# 删除这行：
self.btn_browse2.configure(command=lambda: (self.select_save_folder(), self.e_save.configure(style="TEntry")))
```

因为 `_on_save_dir_change` 已经通过 `trace` 自动处理了样式恢复。

### 修复效果

- ✅ 光标聚焦到"浏览文件"按钮
- ✅ 按钮样式保持正常（文字不消失，大小不变）
- ✅ 输入框变红提示用户
- ✅ 选择文件后，输入框的红色自动消失（通过 `_on_file_change` trace）
- ✅ 选择文件夹后，输入框的红色自动消失（通过 `_on_save_dir_change` trace）

---

## 🔍 问题 2：选择文件夹后光标未移动

### 现象描述

用户选择要保存的文件夹后，光标没有自动移动到下一个需要填写的必填信息输入框。

### 根本原因

**对比两个函数：**

**`select_file`（第 1155 行）— 有聚焦逻辑：**

```python
def select_file(self):
    ...
    self.file_path_var.set(fp)
    self.cfg["last_file_dir"] = os.path.dirname(fp)
    title, author = self.parse_file(fp)
    display_title, _ = normalize_title_for_export(title)
    self.title_var.set(display_title)
    self.author_var.set(author)

    # ✅ 问题2修复：选择文件后，聚焦到下一个空缺字段
    self.after(100, self._focus_next_empty_field)
```

**`select_save_folder`（第 1180 行）— 没有聚焦逻辑：**

```python
def select_save_folder(self):
    init_dir = self.cfg.get("last_save_dir","")
    folder = filedialog.askdirectory(parent=self, initialdir=init_dir)
    if folder:
        self.save_dir_var.set(folder)
        self.cfg["last_save_dir"] = folder
    # ❌ 缺少 _focus_next_empty_field 调用
```

**原因：** 漏写了。

---

## 🔧 修复方案 2

### 具体改动

**在 `select_save_folder` 函数末尾添加聚焦逻辑（第 1186 行）：**

```python
def select_save_folder(self):
    init_dir = self.cfg.get("last_save_dir","")
    folder = filedialog.askdirectory(parent=self, initialdir=init_dir)
    if folder:
        self.save_dir_var.set(folder)
        self.cfg["last_save_dir"] = folder
        # ✅ 选择文件夹后，聚焦到下一个空缺字段
        self.after(100, self._focus_next_empty_field)
```

### 修复效果

- ✅ 用户选择文件夹后，光标自动跳转到下一个必填字段（如联系信息、银行信息等）
- ✅ 与 `select_file` 的行为保持一致

---

## 📝 修改文件清单

**文件：** `/home/rena/projects/submission-tool/app.py`

**修改位置：**

1. **第 1342 行**：新增 `error_style_widgets` 列表声明
2. **第 1354-1359 行**：文件检查分支，分别添加到两个列表
3. **第 1363-1376 行**：标题检查分支，分别添加到两个列表
4. **第 1379-1383 行**：作者检查分支，分别添加到两个列表
5. **第 1387-1390 行**：保存文件夹检查分支，分别添加到两个列表，**删除 command 覆盖**
6. **第 1393-1413 行**：联系信息和银行信息检查分支，分别添加到两个列表
7. **第 1420 行**：样式设置循环改为遍历 `error_style_widgets`
8. **第 1186 行**：`select_save_folder` 函数添加聚焦逻辑

---

## ✅ 验证结果

**语法检查：** 通过

```bash
$ python3 -c "import py_compile; py_compile.compile('app.py', doraise=True); print('语法检查通过')"
语法检查通过
```

---

## 🎯 测试建议

### 测试场景 1：文件未选择

1. 启动程序，不选择文件
2. 点击"导出"按钮
3. **预期：**
   - 弹窗提示"未选择要排版的文件"
   - "浏览文件"按钮样式正常（文字不消失，大小不变）
   - 文件路径输入框变红
   - 光标聚焦到"浏览文件"按钮

4. 点击"浏览文件"按钮，选择文件
5. **预期：**
   - 输入框红色消失
   - 按钮样式保持正常

### 测试场景 2：保存文件夹未选择

1. 启动程序，选择文件但不选择保存文件夹
2. 点击"导出"按钮
3. **预期：**
   - 弹窗提示"保存文件夹为空"
   - "浏览文件夹"按钮样式正常
   - 保存路径输入框变红
   - 光标聚焦到"浏览文件夹"按钮

4. 点击"浏览文件夹"按钮，选择文件夹
5. **预期：**
   - 输入框红色消失
   - 光标自动跳转到下一个必填字段（如联系信息）

### 测试场景 3：多个字段未填写

1. 启动程序，只选择文件，其他字段留空
2. 点击"导出"按钮
3. **预期：**
   - 弹窗列出所有缺失字段
   - 所有未填写的 Entry 输入框变红
   - 所有按钮样式正常
   - 光标聚焦到第一个缺失字段

---

## 📚 经验总结

### 1. ttk 样式系统的陷阱

- **不同控件类型不能共用样式**：`Error.TEntry` 只能用于 `ttk.Entry`，不能用于 `ttk.Button`
- **样式设置要分类处理**：聚焦和样式是两个独立关注点，应该用不同的列表管理

### 2. 为什么 v1.0.33 成功但 v1.0.34 失败？

- v1.0.33 成功是因为**偶然**：聚焦到 `e_file` 意味着按钮不在 `missing_widgets` 中
- v1.0.34 失败是因为**必然**：聚焦到 `btn_browse1` 意味着按钮在 `missing_widgets` 中，必然被错误样式毁掉
- **根本问题从未被解决**：第 1419 行的循环对按钮设置了错误样式

### 3. 一致性原则

- `select_file` 和 `select_save_folder` 应该有相同的行为模式
- 如果一个是选择后聚焦下一个字段，另一个也应该如此

---

## 🔗 相关文件

- **主程序：** `/home/rena/projects/submission-tool/app.py`
- **版本信息：** 当前 v1.0.35，建议更新为 v1.0.36

---

**分析完成时间：** 2026-10-17  
**分析模型：** Qwen3.8 Max  
**状态：** ✅ 修复已完成，待用户测试验证
