from __future__ import annotations

import unittest

from pyylmao.ansi2irc import (
    ansi_to_irc_text,
    detect_ansi_encoding,
    is_ansi2irc_command,
    render_ansi2irc_command,
    strip_sauce,
)


class Ansi2IRCTests(unittest.TestCase):
    def test_detects_cp437_and_strips_sauce_record(self) -> None:
        sauce = b"SAUCE00" + b"x" * 121
        raw = b"\x1b[31m\xb0\xb1\xb2\xdb\xdc\xdd\xde\xdf\x1a" + sauce
        self.assertEqual(strip_sauce(raw), b"\x1b[31m\xb0\xb1\xb2\xdb\xdc\xdd\xde\xdf")
        self.assertEqual(detect_ansi_encoding(strip_sauce(raw)), "cp437")

    def test_ansi_to_irc_handles_sgr_and_cursor_right(self) -> None:
        rendered = ansi_to_irc_text("\x1b[31mRED\x1b[0m\x1b[3CEND")
        self.assertIn("\x0305RED\x03", rendered)
        self.assertIn("   END", rendered)

    def test_render_url_command_outputs_logged_header_and_cp437_text(self) -> None:
        def fetcher(url: str) -> bytes:
            self.assertEqual(url, "https://example.test/a.ans")
            return b"\x1b[31m\xb0\xb1\xb2\x1b[0m\r\nSAUCE00" + b"x" * 121

        lines = render_ansi2irc_command("!ansi2irc https://example.test/a.ans", fetcher=fetcher)
        self.assertEqual(lines[0], "ANSI→IRC (cp437 detected):")
        self.assertIn("░▒▓", "".join(lines[1:]))

    def test_detects_command_forms(self) -> None:
        self.assertTrue(is_ansi2irc_command("!ansi2irc https://example.test/a.ans"))
        self.assertTrue(is_ansi2irc_command("!irc2ansi https://example.test/a.txt"))
        self.assertFalse(is_ansi2irc_command("ansi2irc https://example.test/a.ans"))


if __name__ == "__main__":
    unittest.main()
