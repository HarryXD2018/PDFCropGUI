#!/usr/bin/env python3
"""Command-line automatic cropping: remove page whitespace via ``pdfcrop``.

Each output keeps a physical padding around the content box detected by
``pdfcrop``; the default is 2 mm on all four sides.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from pdfcropper.core import CropError, MarginsMM, find_pdfcrop, run_pdfcrop
except ImportError as exc:  # missing PyMuPDF or an unprepared interpreter
    sys.exit(
        f"无法加载依赖（{exc}）。请先激活环境：\n"
        "  conda activate pdfcropgui\n"
        "或直接使用环境内的 Python 运行本脚本。"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="autocrop",
        description="使用 pdfcrop 自动去除页面空白，四边默认额外保留 2 mm。",
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="待裁剪的 PDF 文件")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="输出文件（仅适用于单个输入）；省略时写入 <原名><后缀>.pdf",
    )
    parser.add_argument(
        "-d",
        "--output-dir",
        type=Path,
        help="输出目录；省略时与输入文件同目录",
    )
    parser.add_argument(
        "-p",
        "--pad",
        type=float,
        default=2.0,
        metavar="MM",
        help="四边统一的额外留白，单位毫米（默认 2）",
    )
    parser.add_argument(
        "--margins",
        nargs=4,
        type=float,
        metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"),
        help="分别指定四边留白（毫米），覆盖 --pad",
    )
    parser.add_argument(
        "--suffix",
        default="_cropped",
        help="默认输出文件名后缀（默认 _cropped）",
    )
    parser.add_argument(
        "--pdfcrop",
        help="pdfcrop 可执行文件路径；省略时在 PATH 中查找",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        metavar="SECONDS",
        help="单个文件的 pdfcrop 超时时间（默认 300 秒）",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="覆盖已存在的输出文件",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="打印 pdfcrop 输出")

    args = parser.parse_args(argv)
    if args.output and len(args.inputs) > 1:
        parser.error("--output 只能用于单个输入文件，多个文件请使用 --output-dir。")
    if args.output and args.output_dir:
        parser.error("--output 与 --output-dir 不能同时使用。")
    return args


def resolve_margins(args: argparse.Namespace) -> MarginsMM:
    values = args.margins if args.margins else [args.pad] * 4
    try:
        return MarginsMM(*values)
    except ValueError as exc:
        sys.exit(f"参数错误：{exc}")


def resolve_output(source: Path, args: argparse.Namespace) -> Path:
    if args.output:
        return args.output
    directory = args.output_dir if args.output_dir else source.parent
    return directory / f"{source.stem}{args.suffix}.pdf"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    margins = resolve_margins(args)

    executable = find_pdfcrop(args.pdfcrop)
    if not executable:
        sys.exit(
            "未找到 pdfcrop。请安装 TeX Live / MacTeX / MiKTeX，"
            "或使用 --pdfcrop 指定可执行文件路径。"
        )

    left, top, right, bottom = margins.as_tuple()
    print(f"pdfcrop: {executable}")
    print(f"留白（mm）: 左 {left:g} 上 {top:g} 右 {right:g} 下 {bottom:g}")

    failures = 0
    for source in args.inputs:
        destination = resolve_output(source, args)
        label = f"{source} -> {destination}"
        if destination.exists() and not args.force:
            print(f"跳过（输出已存在，使用 -f 覆盖）：{label}", file=sys.stderr)
            failures += 1
            continue
        try:
            diagnostics = run_pdfcrop(
                source, destination, margins, executable, timeout=args.timeout
            )
        except CropError as exc:
            print(f"失败：{label}\n  {exc}", file=sys.stderr)
            failures += 1
            continue
        print(f"完成：{label}")
        if args.verbose and diagnostics:
            print(diagnostics)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
