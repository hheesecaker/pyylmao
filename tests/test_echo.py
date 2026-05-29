from __future__ import annotations

import unittest

from pyylmao.echo import is_echo_command, render_echo_command, render_echo_text


class EchoTests(unittest.TestCase):
    def test_detects_echo_command(self) -> None:
        self.assertTrue(is_echo_command("!echo **test**"))
        self.assertFalse(is_echo_command("!echos **test**"))

    def test_strips_simple_inline_markup(self) -> None:
        self.assertEqual(render_echo_text("<b>test</b> and **bold**"), ["test and bold"])
        self.assertEqual(render_echo_text("*italics* __under__ `code`"), ["italics under code"])

    def test_expands_literal_newlines(self) -> None:
        self.assertEqual(
            render_echo_command("!echo 1\\n2\\n3"),
            ["1", "2", "3", "", ""],
        )

    def test_renders_markdown_blockquote_style_seen_in_logs(self) -> None:
        self.assertEqual(
            render_echo_command("!echo > test\\na\\n\\n> b"),
            ["┃ test", "┃ a", "", "┃ b", "", ""],
        )


if __name__ == "__main__":
    unittest.main()
