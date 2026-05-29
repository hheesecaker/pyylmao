from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyylmao.mdcat import (
    MdCatStore,
    is_mdcat_command,
    render_markdown_document,
    render_mdcat_command,
)


class MdCatTests(unittest.TestCase):
    def test_detects_mdcat_command(self) -> None:
        self.assertTrue(is_mdcat_command("!mdcat report.md"))
        self.assertTrue(is_mdcat_command("!mdcat table one.txt"))
        self.assertFalse(is_mdcat_command("!mdcats report.md"))
        self.assertFalse(is_mdcat_command("!mdcat"))

    def test_missing_file_uses_logged_tmp_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = MdCatStore([Path(tmp)], options={})
            self.assertEqual(
                store.render("!mdcat indiancommandments"),
                ["{}", "mdcat: no such file @ /usr/src/app/assets/tmp/indiancommandments"],
            )

    def test_rejects_path_traversal_as_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            (base / "secret.md").write_text("# secret", encoding="utf-8")
            store = MdCatStore([root], options={})
            self.assertEqual(
                store.render("!mdcat ../secret.md"),
                ["{}", "mdcat: no such file @ /usr/src/app/assets/tmp/../secret.md"],
            )

    def test_reads_and_renders_markdown_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "ag.txt").write_text(
                "# Rules\n\n- one **bold** thing\n1. ordered\n> quoted",
                encoding="utf-8",
            )
            store = MdCatStore([directory], options={})
            self.assertEqual(
                store.render("!mdcat ag.txt"),
                ["{}", "𝐑𝐮𝐥𝐞𝐬", "", "  • one bold thing", "  1. ordered", "┃ quoted"],
            )

    def test_renders_pipe_tables_with_logged_separator(self) -> None:
        self.assertEqual(
            render_markdown_document("| Header 1 | Header 2 |\n| --- | --- |\n| Foo | Bar |"),
            [
                "                        ",
                " Header 1 🭍  Header 2 🭍",
                " Foo      🭍  Bar      🭍",
                "🮝🮘🮘🮘🮘🮘🮘🮘🮘🮟 🮝🮘🮘🮘🮘🮘🮘🮘🮘🮟",
            ],
        )

    def test_default_renderer_is_usable_without_configured_directory(self) -> None:
        lines = render_mdcat_command("!mdcat missing.md")
        self.assertTrue(lines[0].startswith("{'syntax':"))
        self.assertEqual(lines[1], "mdcat: no such file @ /usr/src/app/assets/tmp/missing.md")


if __name__ == "__main__":
    unittest.main()
