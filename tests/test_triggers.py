from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyylmao.state import JsonState
from pyylmao.triggers import TriggerStore


class TriggerStoreTests(unittest.TestCase):
    def test_enable_disable_messages_and_aliases(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = TriggerStore(JsonState(Path(tmp.name) / "state.json"))

        self.assertEqual(store.handle("!disable reminder"), ["Trigger reminder is now disabled"])
        self.assertFalse(store.enabled("reminders"))
        self.assertFalse(store.enabled("remindme"))

        self.assertEqual(store.handle("!enable reminders"), ["Trigger reminders is now enabled"])
        self.assertTrue(store.enabled("reminder"))

        self.assertEqual(store.handle("!disable ud"), ["Trigger ud is now disabled"])
        self.assertFalse(store.enabled("urbandict"))
        self.assertEqual(store.handle("!enable urban"), ["Trigger urban does not exist"])

    def test_unknown_trigger_names_match_logged_missing_trigger_response(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state_path = Path(tmp.name) / "state.json"
        store = TriggerStore(JsonState(state_path))

        self.assertEqual(store.handle("!disable newthing"), ["Trigger newthing does not exist"])
        self.assertTrue(TriggerStore(JsonState(state_path)).enabled("newthing"))

    def test_enable_is_an_error_after_explicit_enabled_state(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = TriggerStore(JsonState(Path(tmp.name) / "state.json"))

        self.assertEqual(store.handle("!enable hf"), ["Trigger hf is now enabled"])
        self.assertEqual(store.handle("!enable hf"), ["Error: Command 'hf' is already enabled."])


if __name__ == "__main__":
    unittest.main()
