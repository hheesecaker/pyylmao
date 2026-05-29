from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from pyylmao.gay import GayCommandError, is_gay_command, render_gay_command


class GayTests(unittest.TestCase):
    def test_detects_gay_command_only(self) -> None:
        self.assertTrue(is_gay_command("!gay im heterosexual"))
        self.assertTrue(is_gay_command("!GAY im gay"))
        self.assertFalse(is_gay_command("!gay"))
        self.assertFalse(is_gay_command("!gaytext hello"))
        self.assertFalse(is_gay_command("!gaylord hello"))

    def test_renders_animated_gif_and_returns_public_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lines = render_gay_command(
                "!gay im straight",
                output_dir=tmp,
                base_url="https://cte.pcp.ovh/2",
                filename="gay_fixed.gif",
                frame_count=4,
                size=160,
            )

            path = Path(tmp) / "gay_fixed.gif"
            self.assertEqual(lines, ["https://cte.pcp.ovh/2/gay_fixed.gif"])
            self.assertTrue(path.exists())
            with Image.open(path) as image:
                self.assertEqual(image.size, (160, 160))
                self.assertTrue(getattr(image, "is_animated", False))
                self.assertEqual(image.n_frames, 4)

    def test_long_text_is_wrapped_without_failing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lines = render_gay_command(
                "!gay " + ("supercalifragilisticexpialidocious " * 4),
                output_dir=tmp,
                base_url="https://cte.pcp.ovh",
                filename="gay_long.gif",
                frame_count=2,
                size=140,
            )
            self.assertEqual(lines, ["https://cte.pcp.ovh/gay_long.gif"])

    def test_reads_cloudflared_base_url_file(self) -> None:
        old_base = os.environ.pop("PYYLMAO_WWW_BASE_URL", None)
        old_file = os.environ.get("PYYLMAO_WWW_BASE_URL_FILE")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                base_file = Path(tmp) / "base-url"
                base_file.write_text("https://demo.trycloudflare.com\n", encoding="utf-8")
                os.environ["PYYLMAO_WWW_BASE_URL_FILE"] = str(base_file)
                lines = render_gay_command(
                    "!gay tunnel",
                    output_dir=tmp,
                    filename="gay_tunnel.gif",
                    frame_count=2,
                    size=100,
                )
                self.assertEqual(lines, ["https://demo.trycloudflare.com/gay_tunnel.gif"])
        finally:
            if old_base is not None:
                os.environ["PYYLMAO_WWW_BASE_URL"] = old_base
            if old_file is None:
                os.environ.pop("PYYLMAO_WWW_BASE_URL_FILE", None)
            else:
                os.environ["PYYLMAO_WWW_BASE_URL_FILE"] = old_file

    def test_rejects_unsafe_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(GayCommandError):
                render_gay_command(
                    "!gay hi",
                    output_dir=tmp,
                    filename="../gay.gif",
                )


if __name__ == "__main__":
    unittest.main()
