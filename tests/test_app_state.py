from __future__ import annotations

import unittest

from pdfcropper.app import PDFCropApp
from pdfcropper.core import MarginsMM


class FakeVariable:
    def __init__(self, value: str) -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: object) -> None:
        self.value = str(value)


class FakeWidget:
    def grid(self) -> None:
        pass

    def grid_remove(self) -> None:
        pass

    def configure(self, **_kwargs: object) -> None:
        pass


class AutomaticMarginStateTests(unittest.TestCase):
    def make_app_stub(self) -> PDFCropApp:
        app = object.__new__(PDFCropApp)
        app.mode_var = FakeVariable("auto")
        app.active_margin_mode = "manual"
        app.mode_margins = {"manual": MarginsMM(), "auto": MarginsMM()}
        app.margin_vars = {
            "left": FakeVariable("10"),
            "top": FakeVariable("20"),
            "right": FakeVariable("30"),
            "bottom": FakeVariable("40"),
        }
        app.margin_title_var = FakeVariable("")
        app.reset_button_text_var = FakeVariable("")
        app.status_var = FakeVariable("")
        app.scope_frame = FakeWidget()
        app.remove_outside_frame = FakeWidget()
        app.pdfcrop_frame = FakeWidget()
        app.canvas = FakeWidget()
        app._draw_overlay = lambda: None
        return app

    def test_auto_starts_at_pdfcrop_tight_boundary(self) -> None:
        app = self.make_app_stub()
        PDFCropApp._on_mode_change(app)
        self.assertEqual(app.mode_margins["manual"], MarginsMM(10, 20, 30, 40))
        self.assertEqual(
            tuple(float(variable.get()) for variable in app.margin_vars.values()),
            (0.0, 0.0, 0.0, 0.0),
        )
        self.assertIn("默认 0", app.margin_title_var.get())

    def test_manual_and_auto_margins_are_independent(self) -> None:
        app = self.make_app_stub()
        PDFCropApp._on_mode_change(app)
        for variable in app.margin_vars.values():
            variable.set("2")
        app.mode_var.set("manual")
        PDFCropApp._on_mode_change(app)
        self.assertEqual(app.mode_margins["auto"], MarginsMM(2, 2, 2, 2))
        self.assertEqual(
            tuple(float(variable.get()) for variable in app.margin_vars.values()),
            (10.0, 20.0, 30.0, 40.0),
        )


if __name__ == "__main__":
    unittest.main()
