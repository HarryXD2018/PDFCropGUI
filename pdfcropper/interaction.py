from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlparse

from .core import MarginsMM


Box = tuple[float, float, float, float]


def hit_test_crop_box(
    box: Box,
    x: float,
    y: float,
    *,
    tolerance: float = 9.0,
) -> str | None:
    """Return the crop edge or corner under a canvas point."""

    x0, y0, x1, y1 = box
    near_left = abs(x - x0) <= tolerance and y0 - tolerance <= y <= y1 + tolerance
    near_right = abs(x - x1) <= tolerance and y0 - tolerance <= y <= y1 + tolerance
    near_top = abs(y - y0) <= tolerance and x0 - tolerance <= x <= x1 + tolerance
    near_bottom = abs(y - y1) <= tolerance and x0 - tolerance <= x <= x1 + tolerance

    if near_left and near_top:
        return "top_left"
    if near_right and near_top:
        return "top_right"
    if near_left and near_bottom:
        return "bottom_left"
    if near_right and near_bottom:
        return "bottom_right"
    if near_left:
        return "left"
    if near_right:
        return "right"
    if near_top:
        return "top"
    if near_bottom:
        return "bottom"
    return None


def resize_crop_box(
    box: Box,
    handle: str,
    x: float,
    y: float,
    bounds: Box,
    *,
    minimum_size: float = 12.0,
) -> Box:
    """Move selected crop-box borders while preserving a valid rectangle."""

    x0, y0, x1, y1 = box
    bound_left, bound_top, bound_right, bound_bottom = bounds

    if "left" in handle:
        x0 = max(bound_left, min(x, x1 - minimum_size))
    if "right" in handle:
        x1 = min(bound_right, max(x, x0 + minimum_size))
    if "top" in handle:
        y0 = max(bound_top, min(y, y1 - minimum_size))
    if "bottom" in handle:
        y1 = min(bound_bottom, max(y, y0 + minimum_size))
    return x0, y0, x1, y1


def canvas_box_to_margins(
    box: Box,
    image_bounds: Box,
    page_width_pt: float,
    page_height_pt: float,
) -> MarginsMM:
    """Convert a visual canvas crop box to physical page margins."""

    x0, y0, x1, y1 = box
    image_left, image_top, image_right, image_bottom = image_bounds
    if image_right <= image_left or image_bottom <= image_top:
        raise ValueError("页面预览尺寸无效。")
    if x1 <= x0 or y1 <= y0:
        raise ValueError("裁剪框尺寸无效。")

    x0 = max(image_left, min(x0, image_right))
    x1 = max(image_left, min(x1, image_right))
    y0 = max(image_top, min(y0, image_bottom))
    y1 = max(image_top, min(y1, image_bottom))
    point_to_mm = 25.4 / 72.0
    x_scale = page_width_pt / (image_right - image_left)
    y_scale = page_height_pt / (image_bottom - image_top)
    return MarginsMM(
        left=(x0 - image_left) * x_scale * point_to_mm,
        top=(y0 - image_top) * y_scale * point_to_mm,
        right=(image_right - x1) * x_scale * point_to_mm,
        bottom=(image_bottom - y1) * y_scale * point_to_mm,
    )


def dropped_item_to_path(item: str) -> Path:
    """Convert a native drop item or file URI into a local path."""

    raw = item.strip()
    parsed = urlparse(raw)
    if parsed.scheme.lower() != "file":
        return Path(raw)

    decoded_path = unquote(parsed.path)
    if os.name == "nt":
        if parsed.netloc:
            decoded_path = f"//{parsed.netloc}{decoded_path}"
        elif re.match(r"^/[A-Za-z]:", decoded_path):
            decoded_path = decoded_path[1:]
    elif parsed.netloc:
        decoded_path = f"//{parsed.netloc}{decoded_path}"
    return Path(decoded_path)


def dropped_pdf_paths(items: Iterable[str]) -> list[Path]:
    """Keep PDF files from a native drag payload, preserving its order."""

    paths: list[Path] = []
    for item in items:
        path = dropped_item_to_path(item).expanduser()
        if path.suffix.lower() == ".pdf":
            paths.append(path)
    return paths
