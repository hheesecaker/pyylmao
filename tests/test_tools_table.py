from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from pyylmao.state import JsonState
from pyylmao.tools_table import canonical_tool_name, handle_tool_toggle, render_tools_table, tool_enabled
from pyylmao.command_list import render_command_table


class ToolsTableTests(unittest.TestCase):
    def test_tools_table_matches_logged_modern_shape(self) -> None:
        lines = render_tools_table()
        self.assertEqual(lines[0], "")
        self.assertEqual(lines[1], "                                                                    ")
        self.assertIn(" tool_name         🭍  plugin                            🭍  enabled 🭍", lines)
        self.assertIn(" run               🭍  llm_run_command                   🭍  Yes     🭍", lines)
        self.assertIn(" eval              🭍  llm_eval_tool                     🭍  No      🭍", lines)
        self.assertIn(" update_skill      🭍  llm_skill_tools                   🭍  No      🭍", lines)
        self.assertNotIn(" save_artifact", "\n".join(lines))
        self.assertNotIn(" read_artifact", "\n".join(lines))
        self.assertTrue(lines[-1].startswith("🮝🮘"))

    def test_tool_toggle_updates_state_and_table(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = JsonState(Path(tmp.name) / "state.json")

        self.assertTrue(tool_enabled("run", state))
        self.assertEqual(handle_tool_toggle("-tool run", state), ["disabled:", "✔ run"])
        self.assertFalse(tool_enabled("run", state))
        self.assertIn(" run               🭍  llm_run_command                   🭍  No      🭍", render_tools_table(state))

        self.assertEqual(handle_tool_toggle("+tools +run +remember", state), ["enabled:", "✔ +run", "✔ +remember"])
        self.assertTrue(tool_enabled("run", state))
        self.assertTrue(tool_enabled("+remember", state))

        self.assertTrue(tool_enabled("save_artifact", state))
        self.assertEqual(handle_tool_toggle("-tool save_artifact", state), ["disabled:", "✔ save_artifact"])
        self.assertFalse(tool_enabled("save_artifact", state))

    def test_query_skill_toggle_matches_logged_singular_alias(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = JsonState(Path(tmp.name) / "state.json")

        self.assertEqual(canonical_tool_name("query_skill"), "query_skills")
        self.assertEqual(canonical_tool_name("list_artifact"), "list_artifacts")
        self.assertFalse(tool_enabled("query_skills", state))
        self.assertEqual(handle_tool_toggle("+tool query_skill", state), ["enabled:", "✔ query_skill"])
        self.assertTrue(tool_enabled("query_skills", state))
        self.assertIn(" query_skills      🭍  llm_skill_tools                   🭍  Yes     🭍", render_tools_table(state))

    def test_command_table_includes_generated_command_entries(self) -> None:
        lines = render_command_table(
            lambda name: name != "hello",
            (("hello", True, r"^!hello (.+)$"),),
        )
        table = "\n".join(lines)
        self.assertIn("|    hello     |  False  |", table)
        self.assertIn(r"^!hello (.+)$", table)


if __name__ == "__main__":
    unittest.main()
