from __future__ import annotations

import unittest

from pyylmao.img2irc import (
    HALF_BLOCK,
    RESET_ANSI,
    RESET_IRC,
    Img2IRCOptions,
    img2irc_trigger_name,
    is_img2irc_command,
    parse_img2irc_command,
    render_rgb_matrix,
)


class Img2IRCTests(unittest.TestCase):
    def test_detects_commands_only(self) -> None:
        self.assertTrue(is_img2irc_command("!img2irc https://example.test/a.png"))
        self.assertTrue(is_img2irc_command("!img2irc2 https://example.test/a.png"))
        self.assertTrue(is_img2irc_command("!hax https://example.test/a.png 45 --contrast 1.5"))
        self.assertFalse(is_img2irc_command("!img2ircx https://example.test/a.png"))

    def test_trigger_name_matches_historical_hax_alias(self) -> None:
        self.assertEqual(img2irc_trigger_name("!hax https://example.test/a.png"), "imghax")
        self.assertEqual(img2irc_trigger_name("!img2irc https://example.test/a.png"), "img2irc")

    def test_parses_historical_hax_alias(self) -> None:
        options = parse_img2irc_command("!hax https://pcp.ovh/QbhV.png 45 --contrast 1.5")
        self.assertEqual(options.url, "https://pcp.ovh/QbhV.png")
        self.assertEqual(options.width, 45)
        self.assertEqual(options.contrast, 1.5)

    def test_parses_log_style_options(self) -> None:
        options = parse_img2irc_command(
            "!img2irc https://pcp.ovh/PU65.png width 45 render ansi24 +blocks"
        )
        self.assertEqual(options.url, "https://pcp.ovh/PU65.png")
        self.assertEqual(options.width, 45)
        self.assertEqual(options.render, "ansi24")
        self.assertIn("eighth", options.blocks)

    def test_parses_equals_and_double_dash_options(self) -> None:
        options = parse_img2irc_command(
            "!img2irc2 https://example.test/a.jpg blocks=quarter,half,full,eighth "
            "--width 120 --contrast 30 --saturation 2"
        )
        self.assertEqual(options.width, 120)
        self.assertEqual(options.blocks, ("quarter", "half", "full", "eighth"))
        self.assertEqual(options.contrast, 30)
        self.assertEqual(options.saturation, 2)

    def test_renders_ansi24_half_blocks(self) -> None:
        options = Img2IRCOptions(url="", width=2, render="ansi24")
        lines = render_rgb_matrix(
            [
                [(255, 0, 0), (0, 255, 0)],
                [(0, 0, 255), (255, 255, 255)],
            ],
            options,
        )
        self.assertEqual(len(lines), 1)
        self.assertIn("\x1b[38;2;255;0;0m", lines[0])
        self.assertIn("\x1b[48;2;0;0;255m", lines[0])
        self.assertIn(HALF_BLOCK, lines[0])
        self.assertTrue(lines[0].endswith(RESET_ANSI))

    def test_renders_irc_colors(self) -> None:
        options = Img2IRCOptions(url="", width=2, render="irc")
        lines = render_rgb_matrix(
            [
                [(255, 0, 0), (0, 255, 0)],
                [(0, 0, 255), (255, 255, 255)],
            ],
            options,
        )
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("\x03"))
        self.assertIn(HALF_BLOCK, lines[0])
        self.assertTrue(lines[0].endswith(RESET_IRC))


if __name__ == "__main__":
    unittest.main()
