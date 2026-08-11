from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import fitz


MM_TO_PT = 72.0 / 25.4


class CropError(RuntimeError):
    """Raised when a crop operation cannot be completed safely."""


@dataclass(frozen=True)
class MarginsMM:
    """Physical margins removed from the four sides of a page."""

    left: float = 0.0
    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0

    def __post_init__(self) -> None:
        values = (self.left, self.top, self.right, self.bottom)
        if any(value < 0 for value in values):
            raise ValueError("裁剪边距不能为负数。")

    def as_points(self) -> tuple[float, float, float, float]:
        return tuple(value * MM_TO_PT for value in self.as_tuple())

    def as_tuple(self) -> tuple[float, float, float, float]:
        return self.left, self.top, self.right, self.bottom

    def validate_page(self, width_pt: float, height_pt: float) -> None:
        left, top, right, bottom = self.as_points()
        if left + right >= width_pt:
            raise ValueError("左右裁剪边距之和必须小于页面宽度。")
        if top + bottom >= height_pt:
            raise ValueError("上下裁剪边距之和必须小于页面高度。")


def parse_page_range(expression: str, page_count: int) -> list[int]:
    """Parse one-based page expressions such as ``1-3,5,8-``."""

    if page_count < 1:
        raise ValueError("PDF 中没有可裁剪的页面。")
    text = expression.strip().replace("，", ",")
    if not text:
        raise ValueError("请输入页码范围，例如 1-3,5。")

    pages: set[int] = set()
    for token in text.split(","):
        token = token.strip()
        if not token:
            continue
        if re.fullmatch(r"\d+", token):
            start = end = int(token)
        else:
            match = re.fullmatch(r"(\d*)\s*-\s*(\d*)", token)
            if not match or (not match.group(1) and not match.group(2)):
                raise ValueError(f"无法识别页码范围：{token}")
            start = int(match.group(1)) if match.group(1) else 1
            end = int(match.group(2)) if match.group(2) else page_count
        if start > end:
            raise ValueError(f"页码范围起始值大于结束值：{token}")
        if start < 1 or end > page_count:
            raise ValueError(f"页码必须位于 1 到 {page_count} 之间：{token}")
        pages.update(range(start - 1, end))

    if not pages:
        raise ValueError("没有选择任何页面。")
    return sorted(pages)


def find_pdfcrop(custom_path: str | os.PathLike[str] | None = None) -> str | None:
    """Find a user-selected or PATH-provided pdfcrop executable."""

    if custom_path:
        candidate = Path(custom_path).expanduser()
        if candidate.is_file():
            return str(candidate.resolve())

    for name in ("pdfcrop", "pdfcrop.exe", "pdfcrop.pl"):
        resolved = shutil.which(name)
        if resolved:
            return resolved
    return None


def build_pdfcrop_command(
    executable: str,
    input_pdf: str | os.PathLike[str],
    output_pdf: str | os.PathLike[str],
    margins: MarginsMM,
    *,
    clip: bool = True,
    hires: bool = True,
) -> list[str]:
    """Build a shell-free pdfcrop command.

    pdfcrop uses PostScript points for ``--margins``. Positive values add a
    physical margin around the automatically detected content box.
    """

    prefix: list[str]
    if Path(executable).suffix.lower() == ".pl":
        perl = shutil.which("perl")
        if not perl:
            raise CropError("选择的是 pdfcrop.pl，但系统中未找到 Perl。")
        prefix = [perl, executable]
    else:
        prefix = [executable]

    margin_text = " ".join(f"{value * MM_TO_PT:.5f}" for value in margins.as_tuple())
    command = [*prefix, "--margins", margin_text]
    if clip:
        command.append("--clip")
    if hires:
        command.append("--hires")
    command.extend([str(input_pdf), str(output_pdf)])
    return command


def _temporary_output(final_output: Path) -> Path:
    final_output.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(
        prefix=f".{final_output.stem}_", suffix=".pdf", dir=final_output.parent
    )
    os.close(handle)
    Path(name).unlink(missing_ok=True)
    return Path(name)


def validate_pdf(
    path: str | os.PathLike[str],
    expected_pages: int | None = None,
    *,
    password: str | None = None,
) -> int:
    """Reopen a generated PDF and verify that it contains readable pages."""

    try:
        with fitz.open(path) as document:
            page_count = document.page_count
            if document.needs_pass and (not password or document.authenticate(password) <= 0):
                raise CropError("生成的 PDF 需要密码，且无法使用原密码完成结果校验。")
            if page_count < 1:
                raise CropError("生成的 PDF 不包含页面。")
            if expected_pages is not None and page_count != expected_pages:
                raise CropError(
                    f"生成结果页数异常：应为 {expected_pages} 页，实际为 {page_count} 页。"
                )
            for page_number in range(page_count):
                rectangle = document[page_number].rect
                if rectangle.width <= 1 or rectangle.height <= 1:
                    raise CropError(f"第 {page_number + 1} 页的裁剪区域无效。")
            return page_count
    except CropError:
        raise
    except Exception as exc:
        raise CropError(f"无法读取生成的 PDF：{exc}") from exc


def run_pdfcrop(
    input_pdf: str | os.PathLike[str],
    output_pdf: str | os.PathLike[str],
    margins: MarginsMM,
    executable: str,
    *,
    password: str | None = None,
    timeout: int = 300,
) -> str:
    """Run pdfcrop atomically from an isolated, path-safe work directory.

    pdfcrop attempts to create a symbolic link when an input path contains
    characters outside its conservative safe-name pattern. A normal absolute
    Windows path contains backslashes and therefore enters that branch, where
    link creation may be denied. Staging the source under a simple relative
    name avoids that pdfcrop behavior and also isolates its temporary files.
    """

    source = Path(input_pdf).resolve()
    destination = Path(output_pdf).resolve()
    if not source.is_file():
        raise CropError(f"输入文件不存在：{source}")
    if source == destination:
        raise CropError("请将输出保存为另一个文件，避免覆盖原始 PDF。")

    try:
        with fitz.open(source) as document:
            if document.needs_pass:
                if not password or document.authenticate(password) <= 0:
                    raise CropError("输入 PDF 已加密，密码不正确。")
                raise CropError("pdfcrop 无法安全接收加密 PDF 的密码，请先解密后再自动裁剪。")
            expected_pages = document.page_count
    except CropError:
        raise
    except Exception as exc:
        raise CropError(f"无法打开输入 PDF：{exc}") from exc

    temp_output = _temporary_output(destination)
    try:
        with tempfile.TemporaryDirectory(prefix="pdfcrop_gui_") as work_directory_name:
            work_directory = Path(work_directory_name)
            staged_input = work_directory / "input.pdf"
            staged_output = work_directory / "output.pdf"
            shutil.copyfile(source, staged_input)
            command = build_pdfcrop_command(
                executable,
                staged_input.name,
                staged_output.name,
                margins,
            )
            completed = subprocess.run(
                command,
                cwd=work_directory,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
                shell=False,
            )
            diagnostics = "\n".join(
                part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
            )
            if completed.returncode != 0:
                raise CropError(
                    "pdfcrop 执行失败。\n"
                    + (
                        diagnostics[-3000:]
                        if diagnostics
                        else f"退出代码：{completed.returncode}"
                    )
                )
            if not staged_output.is_file():
                raise CropError("pdfcrop 未生成输出文件。")
            validate_pdf(staged_output, expected_pages)
            shutil.copyfile(staged_output, temp_output)

        validate_pdf(temp_output, expected_pages)
        os.replace(temp_output, destination)
        return diagnostics
    except subprocess.TimeoutExpired as exc:
        raise CropError(f"pdfcrop 在 {timeout} 秒内未完成，操作已取消。") from exc
    except OSError as exc:
        raise CropError(f"自动裁剪的临时文件处理失败：{exc}") from exc
    finally:
        temp_output.unlink(missing_ok=True)


def manual_crop(
    input_pdf: str | os.PathLike[str],
    output_pdf: str | os.PathLike[str],
    margins: MarginsMM,
    page_indices: Sequence[int] | Iterable[int],
    *,
    password: str | None = None,
    remove_outside: bool = False,
) -> None:
    """Crop selected pages with physical margins, preserving other pages.

    Rotated pages are normalized before setting the crop box so that the GUI's
    top-left visual coordinates remain intuitive. If ``remove_outside`` is
    true, page content outside the keep rectangle is first removed with PDF
    redactions before the CropBox is changed.
    """

    source = Path(input_pdf).resolve()
    destination = Path(output_pdf).resolve()
    if not source.is_file():
        raise CropError(f"输入文件不存在：{source}")
    if source == destination:
        raise CropError("请将输出保存为另一个文件，避免覆盖原始 PDF。")

    selected = sorted(set(int(index) for index in page_indices))
    temp_output = _temporary_output(destination)
    try:
        document = fitz.open(source)
        try:
            if document.needs_pass and (not password or document.authenticate(password) <= 0):
                raise CropError("输入 PDF 已加密，密码不正确。")
            if not selected:
                raise CropError("没有选择任何页面。")
            if selected[0] < 0 or selected[-1] >= document.page_count:
                raise CropError("所选页码超出了 PDF 的页数。")

            for index in selected:
                page = document[index]
                if page.rotation:
                    page.remove_rotation()
                page_rect = page.rect
                margins.validate_page(page_rect.width, page_rect.height)
                left, top, right, bottom = margins.as_points()
                base_cropbox = page.cropbox
                keep_rect = fitz.Rect(
                    page_rect.x0 + left,
                    page_rect.y0 + top,
                    page_rect.x1 - right,
                    page_rect.y1 - bottom,
                )
                if remove_outside:
                    _remove_page_content_outside(page, keep_rect, page_rect)
                crop_rect = fitz.Rect(
                    base_cropbox.x0 + left,
                    base_cropbox.y0 + top,
                    base_cropbox.x1 - right,
                    base_cropbox.y1 - bottom,
                )
                page.set_cropbox(crop_rect)

            document.save(
                temp_output,
                garbage=4,
                deflate=True,
                clean=True,
                encryption=fitz.PDF_ENCRYPT_KEEP,
            )
            expected_pages = document.page_count
        finally:
            document.close()

        validate_pdf(temp_output, expected_pages, password=password)
        os.replace(temp_output, destination)
    except CropError:
        raise
    except Exception as exc:
        raise CropError(f"手动裁剪失败：{exc}") from exc
    finally:
        temp_output.unlink(missing_ok=True)


def _rect_is_inside(inner: fitz.Rect, outer: fitz.Rect) -> bool:
    """Return whether a non-empty rectangle is fully inside another one."""

    return not inner.is_empty and outer.contains(inner)


def _remove_page_content_outside(
    page: fitz.Page,
    keep_rect: fitz.Rect,
    page_rect: fitz.Rect,
) -> None:
    """Permanently remove page-level content outside ``keep_rect``.

    Redaction handles text, raster images, and vector graphics. Interactive
    objects that are not fully contained in the keep rectangle are removed as
    well so their actions or payloads do not survive outside the visible page.
    """

    for widget in list(page.widgets() or []):
        if not _rect_is_inside(fitz.Rect(widget.rect), keep_rect):
            page.delete_widget(widget)

    for annotation in list(page.annots() or []):
        if not _rect_is_inside(fitz.Rect(annotation.rect), keep_rect):
            page.delete_annot(annotation)

    for link in list(page.get_links()):
        link_rect = link.get("from")
        if link_rect is not None and not _rect_is_inside(fitz.Rect(link_rect), keep_rect):
            page.delete_link(link)

    outside_rectangles = (
        fitz.Rect(page_rect.x0, page_rect.y0, page_rect.x1, keep_rect.y0),
        fitz.Rect(page_rect.x0, keep_rect.y1, page_rect.x1, page_rect.y1),
        fitz.Rect(page_rect.x0, keep_rect.y0, keep_rect.x0, keep_rect.y1),
        fitz.Rect(keep_rect.x1, keep_rect.y0, page_rect.x1, keep_rect.y1),
    )
    for rectangle in outside_rectangles:
        if rectangle.width > 0 and rectangle.height > 0:
            page.add_redact_annot(rectangle, fill=None, cross_out=False)

    page.apply_redactions(
        images=fitz.PDF_REDACT_IMAGE_PIXELS,
        graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED,
        text=fitz.PDF_REDACT_TEXT_REMOVE,
    )
