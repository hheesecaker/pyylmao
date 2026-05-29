from __future__ import annotations

import importlib
import unittest
from unittest.mock import patch

from pyylmao.helpers import img2irc, md2irc


class HelperCompatibilityTests(unittest.TestCase):
    def test_md2irc_returns_bytes_and_supports_output_fn(self) -> None:
        printed: list[str] = []

        result = md2irc("**bold**\n> quote", output_fn=printed.append)

        self.assertIsInstance(result, bytes)
        self.assertEqual(result.decode("utf-8"), "bold\n┃ quote")
        self.assertEqual(printed, ["bold", "┃ quote"])

    def test_img2irc_helper_maps_logged_kwargs_to_renderer_command(self) -> None:
        calls: list[str] = []

        def fake_render(command: str) -> list[str]:
            calls.append(command)
            return ["line1", "line2"]

        with patch("pyylmao.helpers.img2irc.render_img2irc_command", fake_render):
            result = img2irc(
                "https://example.test/a.png",
                width=40,
                render="ansi24",
                blocks=["quarter", "half"],
                contrast=10,
                font_size=13,
            )

        self.assertEqual(result, "line1\nline2")
        self.assertEqual(
            calls,
            ["!img2irc https://example.test/a.png width 40 render ansi24 blocks quarter,half contrast 10"],
        )

    def test_helper_submodules_exist_for_reload_paths(self) -> None:
        self.assertTrue(hasattr(importlib.import_module("pyylmao.helpers.md2irc"), "md2irc"))
        self.assertTrue(hasattr(importlib.import_module("pyylmao.helpers.img2irc"), "img2irc"))


if __name__ == "__main__":
    unittest.main()
