from __future__ import annotations

import unittest

from pyylmao.cowsay import is_cowsay_command, render_cowsay_command


class CowsayTests(unittest.TestCase):
    def test_detects_command_and_optional_style(self) -> None:
        self.assertTrue(is_cowsay_command("!cowsay hi"))
        self.assertTrue(is_cowsay_command("!cowsay:tux hi"))
        self.assertFalse(is_cowsay_command("!cowsay"))

    def test_renders_observed_speech_bubble_shape(self) -> None:
        self.assertEqual(
            render_cowsay_command("!cowsay hi")[:3],
            [" ____", "< hi >", " ----"],
        )

    def test_collapses_spacing_in_message(self) -> None:
        lines = render_cowsay_command("!cowsay   hi     there")
        self.assertEqual(lines[:3], [" __________", "< hi there >", " ----------"])


if __name__ == "__main__":
    unittest.main()
