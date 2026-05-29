from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyylmao.golem import GolemControlStore, is_golem_control_command, parse_param_value
from pyylmao.state import JsonState


class GolemControlTests(unittest.TestCase):
    def make_store(self) -> GolemControlStore:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return GolemControlStore(JsonState(Path(tmp.name) / "state.json"))

    def test_detects_bang_prompt_control_commands(self) -> None:
        self.assertTrue(is_golem_control_command("!> clear"))
        self.assertTrue(is_golem_control_command("!> temperature=0.7"))
        self.assertFalse(is_golem_control_command("> clear"))
        self.assertFalse(is_golem_control_command("user> hello"))

    def test_clear_reply_matches_logs(self) -> None:
        store = self.make_store()
        self.assertEqual(store.handle("!> clear"), ["* Context cleared *"])

    def test_updates_and_removes_params_in_log_style_dict_order(self) -> None:
        store = self.make_store()
        self.assertEqual(
            store.handle("!> temperature=0.7"),
            ["Parameters updated: {'temperature': 0.7}"],
        )
        self.assertEqual(
            store.handle("!> top_k=0.9"),
            ["Parameters updated: {'temperature': 0.7, 'top_k': 0.9}"],
        )
        self.assertEqual(
            store.handle("!> top_k=0.5"),
            ["Parameters updated: {'temperature': 0.7, 'top_k': 0.5}"],
        )
        self.assertEqual(
            store.handle("!> -top_k"),
            ["Parameters updated: {'temperature': 0.7}"],
        )

    def test_updates_multiple_params_and_preserves_existing_key_position(self) -> None:
        store = self.make_store()
        store.handle("!> temperature=0.7")
        self.assertEqual(
            store.handle("!> repetition_penalty=1.2 min_new_tokens=100 temperature=1.0"),
            [
                "Parameters updated: {'temperature': 1.0, 'repetition_penalty': 1.2, "
                "'min_new_tokens': 100}"
            ],
        )

    def test_unknown_control_command_matches_logs(self) -> None:
        store = self.make_store()
        self.assertEqual(store.handle("!> config"), ["Unknown command: config"])
        self.assertEqual(store.handle("!>> clear"), ["Unknown command: > clear"])

    def test_parse_param_value(self) -> None:
        self.assertEqual(parse_param_value("100"), 100)
        self.assertEqual(parse_param_value("0.7"), 0.7)
        self.assertIs(parse_param_value("True"), True)
        self.assertEqual(parse_param_value("fast"), "fast")


if __name__ == "__main__":
    unittest.main()
