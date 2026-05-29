from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyylmao.ascii_art import AsciiArtStore


class AsciiArtTests(unittest.TestCase):
    def test_directory_lookup_uses_case_sensitive_txt_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "lain.txt").write_text("line one\nline two\n", encoding="utf-8")
            store = AsciiArtStore.default(directory)
            self.assertEqual(store.handle("!ascii lain"), ["line one", "line two"])
            self.assertEqual(store.handle("!ascii Lain"), ["No such file: Lain.txt"])

    def test_rejects_path_traversal_as_missing_file(self) -> None:
        store = AsciiArtStore.default()
        self.assertEqual(store.handle("!ascii ../secret"), ["No such file: ../secret.txt"])


if __name__ == "__main__":
    unittest.main()
