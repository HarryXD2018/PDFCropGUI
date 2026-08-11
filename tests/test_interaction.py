from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pdfcropper.interaction import (
    canvas_box_to_margins,
    dropped_item_to_path,
    dropped_pdf_paths,
    hit_test_crop_box,
    resize_crop_box,
)


class CropBoxInteractionTests(unittest.TestCase):
    def test_detects_four_edges_and_corners(self) -> None:
        box = (100, 100, 300, 400)
        expected = {
            (100, 250): "left",
            (300, 250): "right",
            (200, 100): "top",
            (200, 400): "bottom",
            (100, 100): "top_left",
            (300, 400): "bottom_right",
        }
        for point, handle in expected.items():
            with self.subTest(point=point):
                self.assertEqual(hit_test_crop_box(box, *point), handle)
        self.assertIsNone(hit_test_crop_box(box, 200, 250))

    def test_resizes_only_selected_border(self) -> None:
        box = (100, 100, 300, 400)
        bounds = (0, 0, 500, 600)
        self.assertEqual(resize_crop_box(box, "left", 80, 999, bounds), (80, 100, 300, 400))
        self.assertEqual(
            resize_crop_box(box, "bottom_right", 350, 450, bounds),
            (100, 100, 350, 450),
        )

    def test_prevents_edge_crossing(self) -> None:
        box = (100, 100, 300, 400)
        resized = resize_crop_box(box, "left", 500, 200, (0, 0, 500, 600), minimum_size=20)
        self.assertEqual(resized, (280, 100, 300, 400))

    def test_converts_canvas_box_to_millimetres(self) -> None:
        margins = canvas_box_to_margins(
            (10, 20, 180, 260),
            (0, 0, 200, 300),
            200,
            300,
        )
        self.assertAlmostEqual(margins.left, 10 * 25.4 / 72)
        self.assertAlmostEqual(margins.top, 20 * 25.4 / 72)
        self.assertAlmostEqual(margins.right, 20 * 25.4 / 72)
        self.assertAlmostEqual(margins.bottom, 40 * 25.4 / 72)


class FileDropTests(unittest.TestCase):
    def test_decodes_file_uri(self) -> None:
        self.assertEqual(dropped_item_to_path("file:///tmp/My%20File.pdf"), Path("/tmp/My File.pdf"))

    def test_filters_pdf_files_case_insensitively(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            items = [str(root / "one.PDF"), str(root / "notes.txt"), str(root / "two.pdf")]
            self.assertEqual(dropped_pdf_paths(items), [root / "one.PDF", root / "two.pdf"])
