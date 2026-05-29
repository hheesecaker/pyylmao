from __future__ import annotations

import unittest

from pyylmao.figlet import is_figlet_command, render_figlet_command


class FigletTests(unittest.TestCase):
    def test_command_detection_matches_logged_pattern(self) -> None:
        self.assertTrue(is_figlet_command("!figlet Calvin_S WHO"))
        self.assertTrue(is_figlet_command("!fg Calvin_S WHO"))
        self.assertTrue(is_figlet_command("!faglet Calvin_S WHO"))
        self.assertFalse(is_figlet_command("!figlet"))
        self.assertFalse(is_figlet_command("!figlets Calvin_S WHO"))

    def test_calvin_s_fallback_matches_logged_output_shape(self) -> None:
        self.assertEqual(
            render_figlet_command("!figlet Calvin_S WHO"),
            [
                "╦ ╦╦ ╦╔═╗",
                "║║║╠═╣║ ║",
                "╚╩╝╩ ╩╚═╝",
            ],
        )

    def test_calvin_s_lowercase_matches_logged_output_shape(self) -> None:
        self.assertEqual(
            render_figlet_command("!figlet Calvin_S who"),
            [
                "┬ ┬┬ ┬┌─┐",
                "│││├─┤│ │",
                "└┴┘┴ ┴└─┘",
            ],
        )

    def test_missing_and_unsafe_fonts_use_logged_error(self) -> None:
        self.assertEqual(
            render_figlet_command("!figlet missing text"),
            ["Error: Font 'missing' not found."],
        )
        self.assertEqual(
            render_figlet_command("!figlet ../../../../../../../ text"),
            ["Error: Font '../../../../../../../' not found."],
        )


if __name__ == "__main__":
    unittest.main()
