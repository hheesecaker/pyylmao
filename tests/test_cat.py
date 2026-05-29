from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyylmao.cat import CatFileStore, is_cat_command, render_cat_command


class CatCommandTests(unittest.TestCase):
    def test_detects_cat_command_without_matching_prefixes(self) -> None:
        self.assertTrue(is_cat_command("!cat buflen.txt"))
        self.assertTrue(is_cat_command("!cat file name.txt"))
        self.assertFalse(is_cat_command("!category buflen.txt"))
        self.assertFalse(is_cat_command("!cat"))

    def test_reads_configured_file_without_appending_txt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "buflen.txt").write_text("AAAA\nBBBB\n", encoding="utf-8")
            store = CatFileStore.default(directory)
            self.assertEqual(store.render("!cat buflen.txt"), ["AAAA", "BBBB"])
            self.assertEqual(store.render("!cat buflen"), ["No such file: buflen"])

    def test_missing_file_uses_log_style_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = CatFileStore.default(Path(tmp))
            self.assertEqual(store.render("!cat missing.txt"), ["No such file: missing.txt"])

    def test_rejects_absolute_and_parent_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            directory = base / "root"
            directory.mkdir()
            outside = base / "secret.txt"
            outside.write_text("secret", encoding="utf-8")

            store = CatFileStore.default(directory)
            self.assertEqual(store.render("!cat ../secret.txt"), ["No such file: ../secret.txt"])
            self.assertEqual(store.render("!cat /etc/passwd"), ["No such file: /etc/passwd"])

    def test_truncates_long_output_like_other_text_dump_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "long.txt").write_text("0\n1\n2\n3\n", encoding="utf-8")
            store = CatFileStore([directory], max_lines=2)
            self.assertEqual(
                store.render("!cat long.txt"),
                ["0", "1", "error: output truncated to 2 of 4 lines total"],
            )

    def test_default_renderer_is_usable_without_configured_directory(self) -> None:
        self.assertEqual(render_cat_command("!cat missing.txt"), ["No such file: missing.txt"])


if __name__ == "__main__":
    unittest.main()
