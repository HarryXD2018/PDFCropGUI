# PDFCropGUI

![Version](https://img.shields.io/badge/version-1.3.0-2563eb)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-555)

[简体中文](README.md) | **English**

A lightweight visual PDF cropping tool with mouse selection, independently draggable borders, millimeter-level adjustment, page-range cropping, and native file drag-and-drop. Its automatic mode integrates `pdfcrop` to detect and remove page whitespace.

> The current application interface is Chinese-localized. This document provides complete English setup and operating instructions.

## Highlights

- Draw any keep area directly on the PDF preview;
- Drag the left, top, right, and bottom borders independently, or drag a corner to adjust two borders at once;
- Enter exact crop amounts in millimeters;
- Optionally remove outside-page content by redacting text, image pixels, and vector graphics while rewriting the PDF;
- Apply manual cropping to all pages, the current page, or a custom range such as `1-3,5,8-`;
- Drop PDF files directly into the window, including paths containing spaces or non-ASCII characters;
- Use `pdfcrop` to detect each page's content boundary, with `0 mm` extra margin by default;
- Keep manual and automatic margin values separate when switching modes;
- Handle multi-page PDFs, rotated pages, existing CropBoxes, and password-protected PDFs in manual mode;
- Validate the generated PDF before replacing the destination file;
- Run on Windows, macOS, and Linux.

## Cropping Modes

| Item | Manual mode | Automatic mode |
| --- | --- | --- |
| Engine | PyMuPDF / CropBox or Redaction | `pdfcrop` + Ghostscript |
| Crop source | User selection or millimeter values | Actual content boundary on each page |
| Meaning of values | Amount removed from each page edge | Extra whitespace retained around detected content |
| Default | `0 mm`, keep the whole page | `0 mm`, use the tight detected boundary |
| Page scope | All, current, or custom pages | All pages |
| Requires `pdfcrop` | No | Yes |

By default, manual mode only changes the PDF CropBox, so outside objects remain in the file. When **Delete content outside the crop box** is enabled, the application uses PyMuPDF Redaction to remove outside text, erase outside image pixels, remove intersecting vector objects and outside interactive objects, then sets the CropBox and fully rewrites the PDF.

## Windows Quick Start

1. Install [Python 3.10 or later](https://www.python.org/downloads/) and enable **Add Python to PATH** during installation.
2. Download or clone this repository.
3. Double-click `run.bat`.
4. Click `打开 PDF` (**Open PDF**) or drop a PDF into the window, then choose manual or automatic mode.

On first launch, the script creates a `.venv` environment and installs the required packages. Running `run.bat` again after overwriting an older release also installs dependencies introduced by the new version.

Manual mode does not require `pdfcrop`. Automatic mode additionally requires:

- [TeX Live](https://tug.org/texlive/), [MacTeX](https://tug.org/mactex/), or [MiKTeX](https://miktex.org/download);
- [Ghostscript](https://ghostscript.com/releases/gsdnld.html).

Check the installation from Command Prompt:

```bat
pdfcrop --version
gswin64c --version
```

If PDFCropGUI cannot locate `pdfcrop`, switch to `自动裁剪` (**Automatic crop**) and click `选择程序…` (**Select executable...**). Common Windows locations include:

```text
C:\Program Files\MiKTeX\miktex\bin\x64\pdfcrop.exe
C:\texlive\<version>\bin\windows\pdfcrop.exe
```

## Usage

### Manual Cropping

1. Open or drop a PDF.
2. Draw the keep area on the preview. The area inside the red dashed rectangle remains visible.
3. Drag a red border to adjust one edge, or drag a white corner handle to adjust two edges.
4. For exact control, enter the left, top, right, and bottom crop amounts in millimeters.
5. Select all pages, the current page, or a custom page range.
6. Enable `删除框外页面内容（重写 PDF，较慢）` (**Delete content outside the crop box**) if the outside data must be removed.
7. Choose a new output file and start cropping.

When **All pages** is selected for pages of different sizes, the program applies the same physical margins rather than the same proportions.

Deletion mode prevents outside content from reappearing merely by restoring the CropBox, but it is not complete PDF sanitization. It does not automatically remove metadata, attachments, unprocessed pages, or duplicate content elsewhere. Text, images, or vector objects crossing the crop boundary may be partially erased or removed in full, so retain the source and inspect the result.

### Automatic Cropping

1. Switch to **Automatic crop**.
2. Leave all four values at `0 mm` to use the tight boundary detected by `pdfcrop`.
3. Enter positive values, such as `2 mm`, to retain whitespace around the detected content.
4. Select an output file and start cropping.

The program stages the input PDF in an isolated temporary directory and invokes `pdfcrop` with a safe relative filename. This avoids the Windows `Link ... failed (Operation not permitted)` error triggered by special paths and also isolates temporary files created by `pdfcrop`.

## macOS / Linux Quick Start (conda)

`run.sh` manages a conda environment automatically on macOS and Linux:

```bash
./run.sh
```

On first run it checks for `conda`, creates the `pdfcropgui` environment (`python=3.11` plus `tk`) if needed, installs `requirements.txt` from the internal mirror when the dependency marker is missing, and then starts the GUI. Later runs skip straight to launching.

| Variable | Default | Purpose |
| --- | --- | --- |
| `PDFCROPGUI_ENV` | `pdfcropgui` | conda environment name |
| `PDFCROPGUI_PIP_INDEX` | `https://pypi.corp.kuaishou.com/kuaishou/prod` | pip index; `--trusted-host` is derived from it |

Manual setup:

```bash
conda create -n pdfcropgui python=3.11 tk
conda activate pdfcropgui
pip install -i https://pypi.corp.kuaishou.com/kuaishou/prod \
  --trusted-host pypi.corp.kuaishou.com -r requirements.txt
```

## Command-Line Cropping

### `run_cli.sh`: the common case

```bash
./run_cli.sh document.pdf
```

The first argument is the input path. It runs the automatic mode: `pdfcrop` detects each content box, `2 mm` is added on all four sides, and the result is written next to the input as `document_cropped.pdf`. The script also prepares the conda environment, and any further `autocrop.py` options are passed through:

```bash
./run_cli.sh document.pdf -p 0        # tight box, no padding
./run_cli.sh document.pdf -d out/     # write into out/
./run_cli.sh document.pdf -f          # overwrite an existing output
```

### `autocrop.py`: full options

`autocrop.py` reuses the same `pdfcrop` pipeline as the GUI's automatic mode (isolated temp directory, validation by reopening, atomic replace). It needs an active environment:

```bash
conda activate pdfcropgui
python autocrop.py document.pdf
```

| Option | Description |
| --- | --- |
| `inputs` | One or more PDF files |
| `-p, --pad MM` | Uniform padding on all sides, default `2` |
| `--margins L T R B` | Per-side padding in millimeters, overrides `--pad` |
| `-o, --output` | Explicit output file, single input only |
| `-d, --output-dir` | Output directory, defaults to the input's directory |
| `--suffix` | Output suffix, default `_cropped` |
| `-f, --force` | Overwrite existing outputs |
| `--pdfcrop` | Path to the `pdfcrop` executable |
| `--timeout SECONDS` | Per-file timeout, default `300` |
| `-v, --verbose` | Print `pdfcrop` output |

An existing output is skipped unless `-f` is given; the script exits non-zero when any file fails or is skipped, so batch runs can check the result.

### Manual virtual environment

```bash
python -m venv .venv
```

Windows:

```bat
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

macOS / Linux:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

You can also install the application as a command:

```bash
python -m pip install .
pdfcrop-gui
```

## Build a Windows EXE

On Windows, double-click:

```text
build_exe.bat
```

The executable is created at:

```text
dist\PDFCropGUI.exe
```

The EXE includes the interface, drag-and-drop resources, and manual cropping dependencies. It does not bundle TeX Live, MiKTeX, or Ghostscript, so computers using automatic mode must still provide `pdfcrop`.

## Tests

```bash
python -m unittest discover -s tests -v
```

The current test suite covers:

- Border and corner hit testing, independent resizing, and minimum crop-box size;
- Dropped file paths and file URI parsing;
- The automatic tight-boundary default and separation of manual/automatic margins;
- Page-range parsing;
- `pdfcrop` command construction and path-safe temporary staging;
- Selected pages, rotated pages, existing CropBoxes, and encrypted PDFs;
- The recoverability difference between regular CropBox cropping and deletion mode;
- Rendered removal of outside image pixels and vector graphics;
- Reopening output PDFs and validating page counts and dimensions.

## Project Layout

| Path | Purpose |
| --- | --- |
| `README.md` / `README_EN.md` | Chinese and English project documentation |
| `main.py` | Application entry point |
| `pdfcropper/app.py` | Tkinter interface and interaction logic |
| `pdfcropper/core.py` | `pdfcrop` adapter, manual cropping, and PDF validation |
| `pdfcropper/interaction.py` | Pure crop-box and file-drop logic |
| `tests/` | Unit tests |
| `run.bat` | One-click Windows launcher |
| `run.sh` | One-click macOS / Linux launcher (conda, creates env and installs deps) |
| `run_cli.sh` | Shortcut for command-line auto cropping (2 mm padding) |
| `autocrop.py` | Command-line auto cropping with full options |
| `build_exe.bat` | Windows EXE build script |
| `hook-tkinterdnd2.py` | PyInstaller hook for drag-and-drop resources |

## Troubleshooting

### pdfcrop was not found

Install TeX Live, MacTeX, or MiKTeX and verify that `pdfcrop --version` works in a terminal. You may also select `pdfcrop.exe` or `pdfcrop.pl` manually in the application.

### Automatic cropping reports Operation not permitted

Use v1.2.0 or later. Recent versions do not pass a Windows absolute path directly to `pdfcrop`; they use a safe temporary filename instead.

### File drag-and-drop is unavailable

Run `run.bat` again, or install the complete dependency set:

```bash
python -m pip install -r requirements.txt
```

### An encrypted PDF cannot be cropped automatically

`pdfcrop` cannot safely receive an interactive PDF password. Use manual mode, or save an unencrypted copy with a trusted application first.

### Does manual mode also invoke pdfcrop?

No. PyMuPDF handles manual mode: regular cropping only sets the CropBox, while the deletion option applies PDF Redaction to outside page content. Only automatic mode invokes the external `pdfcrop` program.

### Does deletion mode completely sanitize sensitive information?

Not by itself. It removes page content outside the selected crop rectangle and fully rewrites the file with garbage collection, but it does not proactively remove metadata, attachments, unselected pages, or duplicates elsewhere. Use a dedicated PDF sanitization workflow for high-sensitivity documents.

### A digital signature becomes invalid

Resaving a PDF usually invalidates its existing digital signature. Do not process documents whose signature must remain valid.

## Changelog

- **v1.3.0**: Added manual deletion of content outside the crop box through PDF Redaction and full-file rewriting, with recovery, text, image, and vector-content tests.
- **v1.2.0**: Fixed `pdfcrop` link failures caused by Windows special paths; made the tight automatic boundary the default; separated manual and automatic settings.
- **v1.1.0**: Added independently draggable borders/corners and native file drag-and-drop.
- **v1.0.0**: Initial release with preview, page-aware manual cropping, and `pdfcrop` automatic cropping.

## Contributing

Issues and pull requests are welcome. When reporting a bug, include the operating system, Python version, PDFCropGUI version, and the output of `pdfcrop --version`. Do not upload PDFs containing private or sensitive information.
