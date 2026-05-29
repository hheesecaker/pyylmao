from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyylmao.state import JsonState
from pyylmao.todo import TodoStore, is_todo_command


class TodoTests(unittest.TestCase):
    def test_detects_todo_command(self) -> None:
        self.assertTrue(is_todo_command("!todo cut this over"))
        self.assertTrue(is_todo_command("!todo"))
        self.assertFalse(is_todo_command("!todos"))

    def test_adds_and_lists_per_nick(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = TodoStore(JsonState(Path(tmp.name) / "state.json"))

        self.assertEqual(
            store.handle("tinky", "!todo finish spotifm refactor"),
            ["tinky's Todos", "1. ● finish spotifm refactor"],
        )
        self.assertEqual(
            store.handle("tinky", "!todo cause meaningful damage to tiktok"),
            [
                "tinky's Todos",
                "1. ● finish spotifm refactor",
                "2. ● cause meaningful damage to tiktok",
            ],
        )
        self.assertEqual(store.handle("alice", "!todo"), ["alice's Todos"])

    def test_persists_todos(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state_path = Path(tmp.name) / "state.json"
        store = TodoStore(JsonState(state_path))
        store.handle("CIA_WHISTLEBLOWER", "!todo check antennas")

        reloaded = TodoStore(JsonState(state_path))
        self.assertEqual(
            reloaded.handle("CIA_WHISTLEBLOWER", "!todo"),
            ["CIA_WHISTLEBLOWER's Todos", "1. ● check antennas"],
        )


if __name__ == "__main__":
    unittest.main()
