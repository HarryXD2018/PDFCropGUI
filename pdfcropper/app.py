from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import fitz
from PIL import Image, ImageTk
from tkinterdnd2 import COPY, DND_FILES, TkinterDnD

from . import __version__
from .core import (
    CropError,
    MarginsMM,
    find_pdfcrop,
    manual_crop,
    parse_page_range,
    run_pdfcrop,
)
from .interaction import (
    canvas_box_to_margins,
    dropped_pdf_paths,
    hit_test_crop_box,
    resize_crop_box,
)


APP_TITLE = f"PDF 自由裁剪工具 {__version__}"


def _settings_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "PDFCropGUI" / "settings.json"


class PDFCropApp(TkinterDnD.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1180x780")
        self.minsize(940, 640)

        self.document: fitz.Document | None = None
        self.input_path: Path | None = None
        self.password: str | None = None
        self.page_index = 0
        self.preview_photo: ImageTk.PhotoImage | None = None
        self.image_bounds: tuple[float, float, float, float] | None = None
        self.drag_start: tuple[float, float] | None = None
        self.drag_mode: str | None = None
        self.drag_original_box: tuple[float, float, float, float] | None = None
        self.drag_rectangle: int | None = None
        self.render_job: str | None = None
        self.busy = False
        self.worker_results: queue.Queue[tuple[Path, Exception | None]] = queue.Queue()

        self.mode_var = tk.StringVar(value="manual")
        self.scope_var = tk.StringVar(value="all")
        self.custom_pages_var = tk.StringVar(value="1-")
        self.page_status_var = tk.StringVar(value="未打开 PDF")
        self.status_var = tk.StringVar(value="打开一个 PDF 后即可开始。")
        self.margin_title_var = tk.StringVar(value="从页面四边裁去的长度（mm）")
        self.pdfcrop_status_var = tk.StringVar(value="正在检测 pdfcrop…")
        self.zoom_var = tk.DoubleVar(value=1.0)
        self.margin_vars = {
            "left": tk.StringVar(value="0.00"),
            "top": tk.StringVar(value="0.00"),
            "right": tk.StringVar(value="0.00"),
            "bottom": tk.StringVar(value="0.00"),
        }
        self.mode_margins = {"manual": MarginsMM(), "auto": MarginsMM()}
        self.active_margin_mode = "manual"
        self.reset_button_text_var = tk.StringVar(value="重置为整页")
        self.pdfcrop_path_var = tk.StringVar()

        self._load_settings()
        self._build_ui()
        self._enable_file_drop()
        self._bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(50, self._detect_pdfcrop)

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names() and sys.platform == "win32":
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("TkDefaultFont", 11, "bold"))
        style.configure("Muted.TLabel", foreground="#555555")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self, padding=(10, 8))
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(2, weight=1)

        self.open_button = ttk.Button(toolbar, text="打开 PDF", command=self.open_pdf)
        self.open_button.grid(row=0, column=0, padx=(0, 8))
        ttk.Button(toolbar, text="重新载入", command=self.reload_pdf).grid(
            row=0, column=1, padx=(0, 12)
        )
        self.file_label = ttk.Label(toolbar, text="尚未选择文件", style="Muted.TLabel")
        self.file_label.grid(row=0, column=2, sticky="w")

        main = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        main.grid(row=1, column=0, sticky="nsew", padx=10)

        preview_frame = ttk.Frame(main)
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        main.add(preview_frame, weight=4)

        self.canvas = tk.Canvas(
            preview_frame,
            background="#2d3136",
            highlightthickness=0,
            cursor="crosshair",
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", self._schedule_render)
        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._finish_drag)
        self.canvas.bind("<Motion>", self._update_canvas_cursor)

        navigation = ttk.Frame(preview_frame, padding=(0, 8, 0, 0))
        navigation.grid(row=1, column=0, sticky="ew")
        navigation.columnconfigure(3, weight=1)
        ttk.Button(navigation, text="◀ 上一页", command=self.previous_page).grid(row=0, column=0)
        ttk.Button(navigation, text="下一页 ▶", command=self.next_page).grid(
            row=0, column=1, padx=(6, 12)
        )
        ttk.Label(navigation, textvariable=self.page_status_var).grid(row=0, column=2)
        ttk.Label(navigation, text="缩放").grid(row=0, column=4, padx=(12, 5))
        zoom = ttk.Scale(
            navigation,
            from_=0.5,
            to=2.5,
            variable=self.zoom_var,
            command=lambda _value: self._schedule_render(),
            length=130,
        )
        zoom.grid(row=0, column=5)
        ttk.Button(navigation, text="适合窗口", command=self.reset_zoom).grid(
            row=0, column=6, padx=(6, 0)
        )

        controls = ttk.Frame(main, padding=(12, 0, 0, 0), width=330)
        controls.columnconfigure(0, weight=1)
        main.add(controls, weight=1)

        mode_frame = ttk.LabelFrame(controls, text="1. 裁剪方式", padding=10)
        mode_frame.grid(row=0, column=0, sticky="ew")
        mode_frame.columnconfigure(0, weight=1)
        ttk.Radiobutton(
            mode_frame,
            text="手动裁剪：框选或拖动四边/角点",
            variable=self.mode_var,
            value="manual",
            command=self._on_mode_change,
        ).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(
            mode_frame,
            text="自动裁剪：由 pdfcrop 检测内容",
            variable=self.mode_var,
            value="auto",
            command=self._on_mode_change,
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        margin_frame = ttk.LabelFrame(controls, text="2. 裁剪尺寸", padding=10)
        margin_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        margin_frame.columnconfigure(1, weight=1)
        margin_frame.columnconfigure(3, weight=1)
        ttk.Label(margin_frame, textvariable=self.margin_title_var, style="Muted.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 8)
        )
        labels = (("左", "left"), ("上", "top"), ("右", "right"), ("下", "bottom"))
        for index, (label, key) in enumerate(labels):
            row, col = divmod(index, 2)
            ttk.Label(margin_frame, text=label).grid(row=row + 1, column=col * 2, padx=(0, 5))
            entry = ttk.Entry(margin_frame, textvariable=self.margin_vars[key], width=9)
            entry.grid(row=row + 1, column=col * 2 + 1, sticky="ew", padx=(0, 10), pady=3)
            entry.bind("<Return>", self._margin_entry_changed)
            entry.bind("<FocusOut>", self._margin_entry_changed)
        ttk.Button(
            margin_frame,
            textvariable=self.reset_button_text_var,
            command=self.reset_margins,
        ).grid(
            row=3, column=0, columnspan=4, sticky="ew", pady=(8, 0)
        )

        self.scope_frame = ttk.LabelFrame(controls, text="3. 作用页面", padding=10)
        self.scope_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.scope_frame.columnconfigure(1, weight=1)
        ttk.Radiobutton(
            self.scope_frame, text="全部页面", variable=self.scope_var, value="all"
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Radiobutton(
            self.scope_frame, text="仅当前页", variable=self.scope_var, value="current"
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))
        ttk.Radiobutton(
            self.scope_frame, text="指定页码", variable=self.scope_var, value="custom"
        ).grid(row=2, column=0, sticky="w", pady=(5, 0))
        ttk.Entry(self.scope_frame, textvariable=self.custom_pages_var).grid(
            row=2, column=1, sticky="ew", padx=(6, 0), pady=(5, 0)
        )
        ttk.Label(self.scope_frame, text="示例：1-3,5,8-", style="Muted.TLabel").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(4, 0)
        )

        self.pdfcrop_frame = ttk.LabelFrame(controls, text="pdfcrop 状态", padding=10)
        self.pdfcrop_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.pdfcrop_frame.columnconfigure(0, weight=1)
        ttk.Label(
            self.pdfcrop_frame,
            textvariable=self.pdfcrop_status_var,
            wraplength=280,
            style="Muted.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Button(self.pdfcrop_frame, text="选择程序…", command=self.choose_pdfcrop).grid(
            row=1, column=0, sticky="ew", pady=(8, 0), padx=(0, 4)
        )
        ttk.Button(self.pdfcrop_frame, text="重新检测", command=self._detect_pdfcrop).grid(
            row=1, column=1, sticky="ew", pady=(8, 0), padx=(4, 0)
        )

        self.crop_button = ttk.Button(controls, text="选择输出位置并开始裁剪", command=self.crop)
        self.crop_button.grid(row=4, column=0, sticky="ew", pady=(14, 0), ipady=7)
        ttk.Label(
            controls,
            textvariable=self.status_var,
            wraplength=300,
            justify=tk.LEFT,
            style="Muted.TLabel",
        ).grid(row=5, column=0, sticky="ew", pady=(9, 0))

        footer = ttk.Label(
            self,
            text="提示：可将 PDF 拖入窗口；手动模式可框选区域，也可分别拖动四边和角点。",
            padding=(10, 7),
            style="Muted.TLabel",
        )
        footer.grid(row=2, column=0, sticky="ew")

        self._on_mode_change()

    def _enable_file_drop(self) -> None:
        try:
            for widget in (self, self.canvas, self.file_label):
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self._on_file_drop)
        except (tk.TclError, RuntimeError) as exc:
            self.status_var.set(f"文件拖放初始化失败，仍可使用“打开 PDF”：{exc}")

    def _on_file_drop(self, event: object) -> str:
        if self.busy:
            return COPY
        try:
            raw_data = str(getattr(event, "data"))
            items = self.tk.splitlist(raw_data)
            pdf_paths = dropped_pdf_paths(items)
        except (tk.TclError, ValueError, TypeError) as exc:
            messagebox.showerror("无法读取拖入文件", str(exc), parent=self)
            return COPY

        existing = [path for path in pdf_paths if path.is_file()]
        if not existing:
            messagebox.showinfo("不是 PDF 文件", "请拖入一个有效的 PDF 文件。", parent=self)
            return COPY
        self._load_pdf(existing[0])
        if len(existing) > 1:
            self.status_var.set(f"一次仅处理一个文件，已打开：{existing[0].name}")
        return COPY

    def _bind_shortcuts(self) -> None:
        self.bind("<Control-o>", lambda _event: self.open_pdf())
        self.bind("<Control-s>", lambda _event: self.crop())
        self.bind("<Prior>", lambda _event: self.previous_page())
        self.bind("<Next>", lambda _event: self.next_page())

    def _load_settings(self) -> None:
        path = _settings_path()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            selected = data.get("pdfcrop_path", "")
            if isinstance(selected, str):
                self.pdfcrop_path_var.set(selected)
        except (OSError, ValueError, TypeError):
            pass

    def _save_settings(self) -> None:
        path = _settings_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps({"pdfcrop_path": self.pdfcrop_path_var.get()}, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _detect_pdfcrop(self) -> None:
        selected = self.pdfcrop_path_var.get().strip()
        resolved = find_pdfcrop(selected or None)
        if resolved:
            self.pdfcrop_path_var.set(resolved)
            self.pdfcrop_status_var.set(f"已找到：{resolved}")
        else:
            self.pdfcrop_status_var.set(
                "未找到 pdfcrop。手动裁剪仍可使用；自动裁剪需先安装 TeX Live 或 MiKTeX。"
            )
        self._save_settings()

    def choose_pdfcrop(self) -> None:
        initial = self.pdfcrop_path_var.get().strip()
        initial_dir = str(Path(initial).parent) if initial else None
        path = filedialog.askopenfilename(
            title="选择 pdfcrop 程序",
            initialdir=initial_dir,
            filetypes=[
                ("pdfcrop", "pdfcrop*"),
                ("可执行程序", "*.exe *.pl"),
                ("所有文件", "*.*"),
            ],
        )
        if path:
            self.pdfcrop_path_var.set(path)
            self._detect_pdfcrop()

    def open_pdf(self) -> None:
        if self.busy:
            return
        path = filedialog.askopenfilename(
            title="打开 PDF",
            filetypes=[("PDF 文件", "*.pdf"), ("所有文件", "*.*")],
        )
        if path:
            self._load_pdf(Path(path))

    def reload_pdf(self) -> None:
        if self.busy:
            return
        if self.input_path:
            self._load_pdf(self.input_path)

    def _load_pdf(self, path: Path) -> None:
        try:
            document = fitz.open(path)
            password: str | None = None
            if document.needs_pass:
                password = simpledialog.askstring(
                    "PDF 密码", "此 PDF 已加密，请输入打开密码：", show="*", parent=self
                )
                if not password or document.authenticate(password) <= 0:
                    document.close()
                    if password is not None:
                        messagebox.showerror("无法打开", "密码不正确。", parent=self)
                    return
            if document.page_count < 1:
                document.close()
                raise CropError("该 PDF 不包含页面。")
        except Exception as exc:
            messagebox.showerror("无法打开 PDF", str(exc), parent=self)
            return

        if self.document:
            self.document.close()
        self.document = document
        self.input_path = path.resolve()
        self.password = password
        self.page_index = 0
        self.file_label.configure(text=str(self.input_path))
        self.custom_pages_var.set(f"1-{document.page_count}")
        self.mode_margins = {"manual": MarginsMM(), "auto": MarginsMM()}
        self.active_margin_mode = self.mode_var.get()
        self._set_margins(self.mode_margins[self.active_margin_mode])
        if self.active_margin_mode == "auto":
            self.status_var.set("PDF 已载入；自动额外边距为 0 mm，将按内容紧边界裁剪。")
        else:
            self.status_var.set("PDF 已载入。可拖动鼠标选取保留区域。")
        self._render_page()

    def _on_close(self) -> None:
        self._save_settings()
        if self.document:
            self.document.close()
        self.destroy()

    def _on_mode_change(self) -> None:
        new_mode = self.mode_var.get()
        if new_mode != self.active_margin_mode:
            try:
                self.mode_margins[self.active_margin_mode] = self._parse_margin_fields()
            except CropError:
                pass
            self.active_margin_mode = new_mode
            self._set_margins(self.mode_margins[new_mode])

        automatic = new_mode == "auto"
        if automatic:
            self.margin_title_var.set("内容外额外保留边距（mm，默认 0）")
            self.reset_button_text_var.set("恢复 pdfcrop 紧边界")
            self.scope_frame.grid_remove()
            self.pdfcrop_frame.grid()
            self.canvas.configure(cursor="arrow")
            self.status_var.set("默认 0 mm：输出紧贴 pdfcrop 检测到的内容边界。")
        else:
            self.margin_title_var.set("从页面四边裁去的长度（mm）")
            self.reset_button_text_var.set("重置为整页")
            self.scope_frame.grid()
            self.pdfcrop_frame.grid_remove()
            self.canvas.configure(cursor="crosshair")
            self.status_var.set("可重新框选保留区域，也可分别拖动四条边或四个角点。")
        self._draw_overlay()

    def _parse_margin_fields(self) -> MarginsMM:
        try:
            values = {
                key: float(variable.get().strip().replace(",", "."))
                for key, variable in self.margin_vars.items()
            }
            return MarginsMM(**values)
        except ValueError as exc:
            raise CropError(str(exc)) from exc

    def _read_margins(self) -> MarginsMM:
        margins = self._parse_margin_fields()
        if self.document and self.mode_var.get() == "manual":
            try:
                margins.validate_page(
                    self.document[self.page_index].rect.width,
                    self.document[self.page_index].rect.height,
                )
            except ValueError as exc:
                raise CropError(str(exc)) from exc
        return margins

    def _set_margins(self, margins: MarginsMM) -> None:
        for key, value in zip(("left", "top", "right", "bottom"), margins.as_tuple()):
            self.margin_vars[key].set(f"{value:.2f}")
        self.mode_margins[self.active_margin_mode] = margins

    def _margin_entry_changed(self, _event: tk.Event | None = None) -> None:
        try:
            margins = self._read_margins()
        except CropError:
            return
        self.mode_margins[self.active_margin_mode] = margins
        self._draw_overlay()

    def reset_margins(self, render: bool = True) -> None:
        self._set_margins(MarginsMM())
        if render:
            self._draw_overlay()

    def reset_zoom(self) -> None:
        self.zoom_var.set(1.0)
        self._render_page()

    def previous_page(self) -> None:
        if self.document and self.page_index > 0:
            self.page_index -= 1
            self._render_page()

    def next_page(self) -> None:
        if self.document and self.page_index < self.document.page_count - 1:
            self.page_index += 1
            self._render_page()

    def _schedule_render(self, _event: tk.Event | None = None) -> None:
        if self.render_job:
            self.after_cancel(self.render_job)
        self.render_job = self.after(120, self._render_page)

    def _render_page(self) -> None:
        self.render_job = None
        self.canvas.delete("all")
        if not self.document:
            width = max(self.canvas.winfo_width(), 300)
            height = max(self.canvas.winfo_height(), 300)
            self.canvas.create_text(
                width / 2,
                height / 2,
                text="打开 PDF 或将 PDF 拖入此处",
                fill="#d9dde2",
                font=("TkDefaultFont", 14),
            )
            self.page_status_var.set("未打开 PDF")
            self.image_bounds = None
            return

        try:
            page = self.document[self.page_index]
            canvas_width = max(self.canvas.winfo_width() - 36, 200)
            canvas_height = max(self.canvas.winfo_height() - 36, 200)
            fit_scale = min(canvas_width / page.rect.width, canvas_height / page.rect.height)
            scale = max(0.12, min(fit_scale * self.zoom_var.get(), 4.0))
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            self.preview_photo = ImageTk.PhotoImage(image)
            x = self.canvas.winfo_width() / 2
            y = self.canvas.winfo_height() / 2
            self.canvas.create_image(x, y, image=self.preview_photo, anchor=tk.CENTER, tags="page")
            left = x - pixmap.width / 2
            top = y - pixmap.height / 2
            self.image_bounds = (left, top, left + pixmap.width, top + pixmap.height)
            self.page_status_var.set(
                f"第 {self.page_index + 1} / {self.document.page_count} 页   "
                f"{page.rect.width * 25.4 / 72:.1f} × {page.rect.height * 25.4 / 72:.1f} mm"
            )
            self._draw_overlay()
        except Exception as exc:
            self.status_var.set(f"页面预览失败：{exc}")

    def _crop_canvas_box(self, margins: MarginsMM) -> tuple[float, float, float, float] | None:
        if not self.document or not self.image_bounds:
            return None
        image_left, image_top, image_right, image_bottom = self.image_bounds
        page = self.document[self.page_index]
        left, top, right, bottom = margins.as_points()
        x_scale = (image_right - image_left) / page.rect.width
        y_scale = (image_bottom - image_top) / page.rect.height
        return (
            image_left + left * x_scale,
            image_top + top * y_scale,
            image_right - right * x_scale,
            image_bottom - bottom * y_scale,
        )

    def _draw_overlay(self) -> None:
        self.canvas.delete("overlay")
        if self.mode_var.get() != "manual" or not self.image_bounds:
            return
        try:
            box = self._crop_canvas_box(self._read_margins())
        except CropError:
            return
        if not box:
            return
        image_left, image_top, image_right, image_bottom = self.image_bounds
        x0, y0, x1, y1 = box
        shade = "#4b4f54"
        rectangles = (
            (image_left, image_top, image_right, y0),
            (image_left, y1, image_right, image_bottom),
            (image_left, y0, x0, y1),
            (x1, y0, image_right, y1),
        )
        for coordinates in rectangles:
            if coordinates[2] > coordinates[0] and coordinates[3] > coordinates[1]:
                self.canvas.create_rectangle(
                    *coordinates, fill=shade, outline="", stipple="gray50", tags="overlay"
                )
        self.canvas.create_rectangle(
            x0, y0, x1, y1, outline="#ff4f64", width=2, dash=(7, 4), tags="overlay"
        )
        handle_size = 4
        handles = (
            (x0, y0),
            ((x0 + x1) / 2, y0),
            (x1, y0),
            (x0, (y0 + y1) / 2),
            (x1, (y0 + y1) / 2),
            (x0, y1),
            ((x0 + x1) / 2, y1),
            (x1, y1),
        )
        for handle_x, handle_y in handles:
            self.canvas.create_rectangle(
                handle_x - handle_size,
                handle_y - handle_size,
                handle_x + handle_size,
                handle_y + handle_size,
                fill="#ffffff",
                outline="#ff4f64",
                width=1,
                tags="overlay",
            )
        self.canvas.create_text(
            x0 + 8,
            y0 + 8,
            text="保留区域",
            anchor=tk.NW,
            fill="#ff4f64",
            font=("TkDefaultFont", 9, "bold"),
            tags="overlay",
        )

    def _point_in_page(self, x: float, y: float) -> bool:
        if not self.image_bounds:
            return False
        left, top, right, bottom = self.image_bounds
        return left <= x <= right and top <= y <= bottom

    def _clamp_to_page(self, x: float, y: float) -> tuple[float, float]:
        assert self.image_bounds is not None
        left, top, right, bottom = self.image_bounds
        return max(left, min(x, right)), max(top, min(y, bottom))

    def _current_crop_box(self) -> tuple[float, float, float, float] | None:
        try:
            return self._crop_canvas_box(self._read_margins())
        except CropError:
            return None

    def _update_canvas_cursor(self, event: tk.Event) -> None:
        if self.mode_var.get() != "manual" or self.drag_mode:
            return
        box = self._current_crop_box()
        handle = hit_test_crop_box(box, event.x, event.y) if box else None
        if handle in {"left", "right"}:
            cursor = "sb_h_double_arrow"
        elif handle in {"top", "bottom"}:
            cursor = "sb_v_double_arrow"
        elif handle:
            cursor = "fleur"
        else:
            cursor = "crosshair" if self._point_in_page(event.x, event.y) else "arrow"
        try:
            self.canvas.configure(cursor=cursor)
        except tk.TclError:
            self.canvas.configure(cursor="crosshair")

    def _start_drag(self, event: tk.Event) -> None:
        if self.mode_var.get() != "manual" or not self._point_in_page(event.x, event.y):
            return
        self.drag_start = (event.x, event.y)
        current_box = self._current_crop_box()
        self.drag_mode = hit_test_crop_box(current_box, event.x, event.y) if current_box else None
        if not self.drag_mode:
            self.drag_mode = "new"
        self.drag_original_box = current_box
        self.canvas.delete("drag")
        initial_box = current_box if self.drag_mode != "new" and current_box else (
            event.x,
            event.y,
            event.x,
            event.y,
        )
        self.drag_rectangle = self.canvas.create_rectangle(
            *initial_box,
            outline="#21d4a3",
            width=2,
            dash=(5, 3),
            tags="drag",
        )

    def _drag(self, event: tk.Event) -> None:
        if (
            not self.drag_start
            or not self.drag_mode
            or self.drag_rectangle is None
            or not self.image_bounds
        ):
            return
        x, y = self._clamp_to_page(event.x, event.y)
        if self.drag_mode == "new":
            start_x, start_y = self.drag_start
            box = min(start_x, x), min(start_y, y), max(start_x, x), max(start_y, y)
        else:
            assert self.drag_original_box is not None
            box = resize_crop_box(
                self.drag_original_box,
                self.drag_mode,
                x,
                y,
                self.image_bounds,
            )
        self.canvas.coords(self.drag_rectangle, *box)

    def _finish_drag(self, event: tk.Event) -> None:
        if (
            not self.drag_start
            or not self.drag_mode
            or self.drag_rectangle is None
            or not self.image_bounds
            or not self.document
        ):
            return
        self._drag(event)
        coordinates = self.canvas.coords(self.drag_rectangle)
        self.drag_start = None
        drag_mode = self.drag_mode
        self.drag_mode = None
        self.drag_original_box = None
        self.canvas.delete("drag")
        self.drag_rectangle = None
        if len(coordinates) != 4:
            return
        x0, y0, x1, y1 = coordinates
        minimum_size = 12 if drag_mode == "new" else 2
        if x1 - x0 < minimum_size or y1 - y0 < minimum_size:
            self._draw_overlay()
            return
        page = self.document[self.page_index]
        margins = canvas_box_to_margins(
            (x0, y0, x1, y1),
            self.image_bounds,
            page.rect.width,
            page.rect.height,
        )
        self._set_margins(margins)
        self._draw_overlay()

    def _selected_pages(self) -> list[int]:
        assert self.document is not None
        scope = self.scope_var.get()
        if scope == "all":
            return list(range(self.document.page_count))
        if scope == "current":
            return [self.page_index]
        return parse_page_range(self.custom_pages_var.get(), self.document.page_count)

    def crop(self) -> None:
        if self.busy:
            return
        if not self.document or not self.input_path:
            messagebox.showinfo("尚未打开 PDF", "请先打开需要裁剪的 PDF。", parent=self)
            return
        try:
            margins = self._read_margins()
            mode = self.mode_var.get()
            if mode == "manual":
                pages = self._selected_pages()
                for index in pages:
                    page = self.document[index]
                    margins.validate_page(page.rect.width, page.rect.height)
                executable = None
            else:
                pages = []
                executable = find_pdfcrop(self.pdfcrop_path_var.get().strip() or None)
                if not executable:
                    raise CropError(
                        "未找到 pdfcrop。请安装 TeX Live/MiKTeX，或点击“选择程序”指定 pdfcrop。"
                    )
        except (CropError, ValueError) as exc:
            messagebox.showerror("参数有误", str(exc), parent=self)
            return

        default_name = f"{self.input_path.stem}_cropped.pdf"
        output = filedialog.asksaveasfilename(
            title="保存裁剪后的 PDF",
            initialdir=str(self.input_path.parent),
            initialfile=default_name,
            defaultextension=".pdf",
            filetypes=[("PDF 文件", "*.pdf")],
        )
        if not output:
            return
        output_path = Path(output).resolve()
        if output_path == self.input_path:
            messagebox.showerror("不能覆盖原文件", "请选择另一个输出文件名。", parent=self)
            return
        if output_path.exists() and not messagebox.askyesno(
            "覆盖文件", f"{output_path.name} 已存在，是否覆盖？", parent=self
        ):
            return

        self.busy = True
        self.crop_button.configure(state=tk.DISABLED)
        self.open_button.configure(state=tk.DISABLED)
        self.status_var.set("正在裁剪并校验输出，请稍候…")
        source_path = self.input_path
        password = self.password

        def worker() -> None:
            try:
                if mode == "auto":
                    assert executable is not None
                    run_pdfcrop(
                        source_path,
                        output_path,
                        margins,
                        executable,
                        password=password,
                    )
                else:
                    manual_crop(
                        source_path,
                        output_path,
                        margins,
                        pages,
                        password=password,
                    )
                self.worker_results.put((output_path, None))
            except Exception as exc:
                self.worker_results.put((output_path, exc))

        threading.Thread(target=worker, daemon=True).start()
        self.after(100, self._poll_worker)

    def _poll_worker(self) -> None:
        try:
            output_path, error = self.worker_results.get_nowait()
        except queue.Empty:
            if self.busy:
                self.after(100, self._poll_worker)
            return
        self._crop_finished(output_path, error)

    def _crop_finished(self, output_path: Path, error: Exception | None) -> None:
        self.busy = False
        self.crop_button.configure(state=tk.NORMAL)
        self.open_button.configure(state=tk.NORMAL)
        if error:
            self.status_var.set("裁剪失败，原始 PDF 未被修改。")
            messagebox.showerror("裁剪失败", str(error), parent=self)
            return
        self.status_var.set(f"裁剪完成：{output_path}")
        if messagebox.askyesno(
            "裁剪完成", f"文件已保存：\n{output_path}\n\n是否立即打开？", parent=self
        ):
            self._open_external(output_path)

    def _open_external(self, path: Path) -> None:
        try:
            if sys.platform == "win32":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except OSError as exc:
            messagebox.showerror("无法打开文件", str(exc), parent=self)


def main() -> None:
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    app = PDFCropApp()
    app.mainloop()


if __name__ == "__main__":
    main()
