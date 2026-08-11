# PDFCropGUI

![Version](https://img.shields.io/badge/version-1.3.0-2563eb)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-555)

**简体中文** | [English](README_EN.md)

一款轻量、可视化的 PDF 自由裁剪工具。它支持鼠标框选、四边独立拖动、毫米级精调、分页裁剪和文件拖放，并在自动模式中调用 `pdfcrop` 检测和去除页面空白。

## 功能亮点

- 在 PDF 页面预览上拖出任意保留区域；
- 单独拖动左、上、右、下四条边，或拖动角点同时调整相邻两边；
- 使用毫米精确设置四边裁剪量；
- 手动模式可选“删除框外页面内容”，重写 PDF 并移除框外文字、图片像素和矢量对象；
- 手动模式可作用于全部页面、当前页或 `1-3,5,8-` 形式的自定义页码；
- 将 PDF 文件直接拖入窗口，正确处理带空格和非 ASCII 字符的路径；
- 自动模式调用 `pdfcrop` 检测每页内容边界，默认额外边距为 `0 mm`；
- 手动与自动模式分别保存边距，切换模式不会相互污染参数；
- 支持多页、旋转页面、已有 CropBox 和加密 PDF 的手动裁剪；
- 输出校验成功后才替换目标文件，不修改原始 PDF；
- 支持 Windows、macOS 和 Linux。

## 两种裁剪模式

| 项目 | 手动裁剪 | 自动裁剪 |
| --- | --- | --- |
| 处理引擎 | PyMuPDF / CropBox 或 Redaction | `pdfcrop` + Ghostscript |
| 裁剪依据 | 用户框选或毫米数值 | 每页实际内容边界 |
| 数值含义 | 从页面四边裁去的长度 | 内容边界外额外保留的空白 |
| 默认值 | `0 mm`，保留整页 | `0 mm`，紧贴检测到的内容 |
| 页面范围 | 全部、当前页或自定义页码 | 全部页面 |
| 是否依赖 `pdfcrop` | 否 | 是 |

手动模式默认只修改 PDF 的 CropBox，框外对象仍保存在文件中；勾选“删除框外页面内容”后，软件会先用 PyMuPDF Redaction 删除框外文字、擦除框外图片像素、移除相交的矢量对象和框外交互对象，再设置 CropBox 并完整重写 PDF。

## Windows 快速开始

1. 安装 [Python 3.10 或更高版本](https://www.python.org/downloads/)，安装时勾选 **Add Python to PATH**。
2. 下载或克隆本项目。
3. 双击 `run.bat`。
4. 点击“打开 PDF”或将 PDF 拖入窗口，然后选择手动或自动模式。

首次运行时，脚本会创建 `.venv` 虚拟环境并安装依赖。覆盖升级旧版本后再次运行 `run.bat`，脚本也会自动补装新增依赖。

手动裁剪不需要安装 `pdfcrop`。使用自动裁剪时，还需要以下组件：

- [TeX Live](https://tug.org/texlive/)、[MacTeX](https://tug.org/mactex/) 或 [MiKTeX](https://miktex.org/download)；
- [Ghostscript](https://ghostscript.com/releases/gsdnld.html)。

可以在命令提示符中检查：

```bat
pdfcrop --version
gswin64c --version
```

如果程序没有自动找到 `pdfcrop`，进入自动模式后点击“选择程序…”。Windows 常见位置包括：

```text
C:\Program Files\MiKTeX\miktex\bin\x64\pdfcrop.exe
C:\texlive\<版本号>\bin\windows\pdfcrop.exe
```

## 使用方法

### 手动裁剪

1. 打开或拖入 PDF。
2. 在页面预览上拖出保留区域，红色虚线内为最终可见范围。
3. 拖动红色边线可单独调整一边，拖动白色角点可同时调整相邻两边。
4. 如需精确控制，可直接输入左、上、右、下四个毫米数值。
5. 选择全部页面、仅当前页或自定义页码。
6. 如果需要移除框外数据，勾选“删除框外页面内容（重写 PDF，较慢）”。
7. 选择新的输出文件并开始裁剪。

对不同尺寸的页面选择“全部页面”时，软件应用相同的物理边距，而不是相同比例。

删除模式适合避免通过恢复 CropBox 重新看到框外内容，但它不是完整的 PDF 安全清理工具：元数据、附件、未处理页面或同一内容的其他副本不会被自动删除。跨越裁剪边界的文字、图片或矢量对象也可能被部分擦除或整体移除，请保留原文件并检查输出。

### 自动裁剪

1. 切换到“自动裁剪”。
2. 保持四边为 `0 mm`，即可使用 `pdfcrop` 检测到的紧边界。
3. 如果希望内容周围保留空白，输入正的毫米数值，例如 `2 mm`。
4. 选择输出文件并开始裁剪。

程序会把输入 PDF 复制到隔离临时目录，并以安全相对文件名调用 `pdfcrop`。这一流程可避开 Windows 下特殊路径触发的 `Link ... failed (Operation not permitted)` 错误，也会隔离 `pdfcrop` 生成的临时文件。

## 命令行运行

```bash
python -m venv .venv
```

Windows：

```bat
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

macOS / Linux：

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

也可以安装为命令：

```bash
python -m pip install .
pdfcrop-gui
```

## 打包 Windows EXE

在 Windows 上双击：

```text
build_exe.bat
```

生成结果位于：

```text
dist\PDFCropGUI.exe
```

生成的 EXE 包含界面、拖放组件和手动裁剪依赖，但不会捆绑 TeX Live、MiKTeX 或 Ghostscript。目标电脑使用自动模式时仍需安装 `pdfcrop`。

## 测试

```bash
python -m unittest discover -s tests -v
```

当前测试覆盖：

- 裁剪框四边和角点命中、独立缩放及最小尺寸限制；
- 拖入文件路径和文件 URI 解析；
- 自动模式默认紧边界及手动/自动边距隔离；
- 页码范围解析；
- `pdfcrop` 命令构造和安全临时路径；
- 分页、旋转页、已有 CropBox 和加密 PDF；
- 普通 CropBox 裁剪仍可恢复框外内容，而删除模式在恢复页面边界后也无法提取框外文字；
- 删除模式对框外图片像素和矢量图形的实际渲染结果；
- 输出文件重开及页数、页面尺寸校验。

## 项目结构

| 路径 | 说明 |
| --- | --- |
| `README.md` / `README_EN.md` | 中文与英文项目说明 |
| `main.py` | 程序入口 |
| `pdfcropper/app.py` | Tkinter 图形界面与交互逻辑 |
| `pdfcropper/core.py` | `pdfcrop` 调用、手动裁剪和 PDF 校验 |
| `pdfcropper/interaction.py` | 裁剪框和文件拖放的纯逻辑 |
| `tests/` | 单元测试 |
| `run.bat` | Windows 一键运行脚本 |
| `build_exe.bat` | Windows EXE 打包脚本 |
| `hook-tkinterdnd2.py` | PyInstaller 拖放资源收集钩子 |

## 常见问题

### 未找到 pdfcrop

确认已经安装 TeX Live、MacTeX 或 MiKTeX，并在终端执行 `pdfcrop --version`。也可以在软件中手动选择 `pdfcrop.exe` 或 `pdfcrop.pl`。

### 自动裁剪出现 Operation not permitted

请使用 v1.2.0 或更高版本。新版不会直接把 Windows 绝对路径交给 `pdfcrop`，而是使用安全临时文件名。

### 文件拖放不可用

重新运行 `run.bat`，或执行：

```bash
python -m pip install -r requirements.txt
```

### 加密 PDF 无法自动裁剪

`pdfcrop` 不能安全接收交互密码。加密 PDF 可以使用手动模式，或先在可信工具中另存为未加密副本。

### 手动裁剪调用的也是 pdfcrop 吗

不是。手动模式由 PyMuPDF 完成：普通方式只设置 CropBox；勾选删除选项时使用 PDF Redaction 删除框外页面内容。只有自动裁剪模式会调用外部 `pdfcrop`。

### 删除框外内容等于彻底清除敏感信息吗

不完全等同。它会删除所选页面裁剪框外的页面内容，并通过垃圾回收完整重写文件；但不会主动清除元数据、附件、未选页面或其他位置的内容副本。对高敏感文件，仍应使用专门的 PDF 脱敏工具复核。

### 裁剪后数字签名失效

重新保存 PDF 通常会破坏原有数字签名。请勿处理必须保持签名有效的文件。

## 版本记录

- **v1.3.0**：手动模式新增删除框外页面内容选项；通过 Redaction 重写 PDF，并加入可恢复性、文字、图片和矢量内容测试。
- **v1.2.0**：修复 Windows 特殊路径导致的 `pdfcrop` 链接错误；自动模式默认紧边界；手动和自动参数隔离。
- **v1.1.0**：增加四边/角点独立拖动和原生文件拖放。
- **v1.0.0**：初始版本，提供预览、分页手动裁剪和 `pdfcrop` 自动裁剪。

## 参与贡献

欢迎提交 Issue 或 Pull Request。报告问题时，建议附上操作系统、Python 版本、PDFCropGUI 版本，以及 `pdfcrop --version` 的输出。请勿上传包含隐私或敏感信息的 PDF。
