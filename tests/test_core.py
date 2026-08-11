from __future__ import annotations

import os
import stat
import tempfile
import textwrap
import unittest
from pathlib import Path

import fitz

from pdfcropper.core import (
    MM_TO_PT,
    MarginsMM,
    build_pdfcrop_command,
    manual_crop,
    parse_page_range,
    run_pdfcrop,
    validate_pdf,
)


class PageRangeTests(unittest.TestCase):
    def test_mixed_ranges(self) -> None:
        self.assertEqual(parse_page_range("1-3,5,8-", 10), [0, 1, 2, 4, 7, 8, 9])

    def test_chinese_comma_and_duplicates(self) -> None:
        self.assertEqual(parse_page_range("1，3-4,3", 5), [0, 2, 3])

    def test_rejects_invalid_ranges(self) -> None:
        for value in ("", "0", "4-2", "x", "1-9"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_page_range(value, 5)


class CommandTests(unittest.TestCase):
    def test_pdfcrop_command_is_shell_free(self) -> None:
        margins = MarginsMM(1, 2, 3, 4)
        command = build_pdfcrop_command("pdfcrop", "a b.pdf", "c d.pdf", margins)
        self.assertEqual(command[0], "pdfcrop")
        self.assertEqual(command[-2:], ["a b.pdf", "c d.pdf"])
        margin_argument = command[command.index("--margins") + 1]
        self.assertEqual(
            [round(float(value), 4) for value in margin_argument.split()],
            [round(number * MM_TO_PT, 4) for number in (1, 2, 3, 4)],
        )
        self.assertIn("--clip", command)
        self.assertIn("--hires", command)


class CropTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.source = self.directory / "source.pdf"
        document = fitz.open()
        for index in range(2):
            page = document.new_page(width=200, height=300)
            page.insert_text((30, 40), f"Page {index + 1}")
            page.draw_rect(fitz.Rect(20, 20, 180, 280))
        document.save(self.source)
        document.close()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_manual_crop_selected_page_only(self) -> None:
        output = self.directory / "manual.pdf"
        manual_crop(self.source, output, MarginsMM(5, 10, 15, 20), [0])
        self.assertEqual(validate_pdf(output, 2), 2)
        with fitz.open(output) as document:
            first = document[0].rect
            second = document[1].rect
            self.assertAlmostEqual(first.width, 200 - (5 + 15) * MM_TO_PT, places=2)
            self.assertAlmostEqual(first.height, 300 - (10 + 20) * MM_TO_PT, places=2)
            self.assertAlmostEqual(second.width, 200, places=2)
            self.assertAlmostEqual(second.height, 300, places=2)

    def test_manual_crop_respects_existing_cropbox(self) -> None:
        pre_cropped = self.directory / "pre_cropped.pdf"
        with fitz.open(self.source) as document:
            document[0].set_cropbox(fitz.Rect(10, 20, 190, 280))
            document.save(pre_cropped)
        output = self.directory / "recropped.pdf"
        manual_crop(pre_cropped, output, MarginsMM(2, 3, 4, 5), [0])
        with fitz.open(output) as document:
            first = document[0]
            self.assertAlmostEqual(first.rect.width, 180 - 6 * MM_TO_PT, places=2)
            self.assertAlmostEqual(first.rect.height, 260 - 8 * MM_TO_PT, places=2)
            self.assertAlmostEqual(first.cropbox.x0, 10 + 2 * MM_TO_PT, places=2)
            self.assertAlmostEqual(first.cropbox.y0, 20 + 3 * MM_TO_PT, places=2)

    def test_manual_crop_normalizes_rotated_page(self) -> None:
        rotated = self.directory / "rotated.pdf"
        with fitz.open(self.source) as document:
            document[0].set_rotation(90)
            document.save(rotated)
        output = self.directory / "rotated_cropped.pdf"
        manual_crop(rotated, output, MarginsMM(5, 10, 15, 20), [0])
        with fitz.open(output) as document:
            page = document[0]
            self.assertEqual(page.rotation, 0)
            self.assertAlmostEqual(page.rect.width, 300 - 20 * MM_TO_PT, places=2)
            self.assertAlmostEqual(page.rect.height, 200 - 30 * MM_TO_PT, places=2)

    def test_manual_crop_keeps_password(self) -> None:
        encrypted = self.directory / "encrypted.pdf"
        password = "test-password"
        with fitz.open(self.source) as document:
            document.save(
                encrypted,
                encryption=fitz.PDF_ENCRYPT_AES_256,
                owner_pw=password,
                user_pw=password,
            )
        output = self.directory / "encrypted_cropped.pdf"
        manual_crop(encrypted, output, MarginsMM(2, 2, 2, 2), [0], password=password)
        self.assertEqual(validate_pdf(output, 2, password=password), 2)
        with fitz.open(output) as document:
            self.assertTrue(document.needs_pass)

    def test_remove_outside_deletes_text_beyond_cropbox(self) -> None:
        source = self.directory / "sensitive.pdf"
        with fitz.open() as document:
            page = document.new_page(width=300, height=300)
            page.insert_text((15, 25), "OUTSIDE_SECRET")
            page.insert_text((115, 155), "INSIDE_VISIBLE")
            page.draw_rect(fitz.Rect(5, 5, 70, 70), color=(1, 0, 0), fill=(1, 0, 0))
            pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 10, 10), False)
            pixmap.clear_with(0x00FF00)
            page.insert_image(
                fitz.Rect(5, 80, 70, 145),
                stream=pixmap.tobytes("png"),
            )
            document.save(source)

        secure_output = self.directory / "secure.pdf"
        manual_crop(
            source,
            secure_output,
            MarginsMM(35, 35, 35, 35),
            [0],
            remove_outside=True,
        )

        with fitz.open(secure_output) as document:
            page = document[0]
            self.assertIn("INSIDE_VISIBLE", page.get_text())
            self.assertNotIn("OUTSIDE_SECRET", page.get_text())
            page.set_cropbox(page.mediabox)
            self.assertNotIn("OUTSIDE_SECRET", page.get_text())
            rendered = page.get_pixmap(alpha=False)
            self.assertTrue(all(channel > 245 for channel in rendered.pixel(30, 30)))
            self.assertTrue(all(channel > 245 for channel in rendered.pixel(30, 110)))
            self.assertEqual(page.get_drawings(), [])

    def test_regular_crop_keeps_outside_content_recoverable(self) -> None:
        source = self.directory / "recoverable.pdf"
        with fitz.open() as document:
            page = document.new_page(width=300, height=300)
            page.insert_text((15, 25), "OUTSIDE_SECRET")
            page.insert_text((115, 155), "INSIDE_VISIBLE")
            document.save(source)

        regular_output = self.directory / "regular.pdf"
        manual_crop(source, regular_output, MarginsMM(35, 35, 35, 35), [0])

        with fitz.open(regular_output) as document:
            page = document[0]
            self.assertNotIn("OUTSIDE_SECRET", page.get_text())
            page.set_cropbox(page.mediabox)
            self.assertIn("OUTSIDE_SECRET", page.get_text())

    @unittest.skipIf(os.name == "nt", "Executable fixture is POSIX-only")
    def test_pdfcrop_adapter_accepts_successful_output(self) -> None:
        fake = self.directory / "fake_pdfcrop"
        fake.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import os
                from pathlib import Path
                import sys
                import fitz
                assert sys.argv[-2] == "input.pdf"
                assert sys.argv[-1] == "output.pdf"
                assert Path("input.pdf").is_file()
                os.link("input.pdf", "link-test.pdf")
                document = fitz.open(sys.argv[-2])
                for page in document:
                    rectangle = page.cropbox
                    page.set_cropbox(fitz.Rect(
                        rectangle.x0 + 20,
                        rectangle.y0 + 20,
                        rectangle.x1 - 20,
                        rectangle.y1 - 20,
                    ))
                document.save(sys.argv[-1])
                document.close()
                print(f"fake pdfcrop completed in {Path.cwd().name}")
                """
            ),
            encoding="utf-8",
        )
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        output = self.directory / "auto.pdf"
        diagnostics = run_pdfcrop(self.source, output, MarginsMM(1, 1, 1, 1), str(fake))
        self.assertIn("completed", diagnostics)
        self.assertEqual(validate_pdf(output, 2), 2)
        with fitz.open(output) as document:
            self.assertAlmostEqual(document[0].rect.width, 160, places=2)
            self.assertAlmostEqual(document[0].rect.height, 260, places=2)


if __name__ == "__main__":
    unittest.main()
