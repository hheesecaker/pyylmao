from __future__ import annotations

import unittest

from pyylmao.palette import is_palette99_command, render_palette99


class PaletteTests(unittest.TestCase):
    def test_detects_exact_palette99_command(self) -> None:
        self.assertTrue(is_palette99_command("!palette99"))
        self.assertTrue(is_palette99_command("  !PALETTE99  "))
        self.assertFalse(is_palette99_command("!palette"))

    def test_renders_logged_two_digit_rows_with_blank_separators(self) -> None:
        self.assertEqual(
            render_palette99(),
            [
                "0001020304050607080910",
                "",
                "1112131415161718192021",
                "",
                "2223242526272829303132",
                "",
                "3334353637383940414243",
                "",
                "4445464748495051525354",
                "",
                "5556575859606162636465",
                "",
                "6667686970717273747576",
                "",
                "7778798081828384858687",
                "",
                "8889909192939495969798",
                "",
            ],
        )


if __name__ == "__main__":
    unittest.main()
