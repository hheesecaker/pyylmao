from __future__ import annotations

from datetime import datetime, timezone
import tempfile
import unittest
from pathlib import Path

from pyylmao.reminders import ReminderStore, parse_reminder_request
from pyylmao.state import JsonState


class ReminderTests(unittest.TestCase):
    def test_parse_relative_message_before_time(self) -> None:
        now = datetime(2026, 2, 18, 23, 56, 30, tzinfo=timezone.utc)
        parsed = parse_reminder_request("test in 20 seconds", now)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.text, "Test")
        self.assertEqual(parsed.due_at, datetime(2026, 2, 18, 23, 56, 50, tzinfo=timezone.utc))

    def test_parse_relative_message_after_time(self) -> None:
        now = datetime(2026, 5, 21, 9, 11, 33, tzinfo=timezone.utc)
        parsed = parse_reminder_request("in 626 days Did Elon Musk survive longer than Steve Jobs?", now)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.text, "Did Elon Musk survive longer than Steve Jobs?")
        self.assertEqual(parsed.due_at, datetime(2028, 2, 6, 9, 11, 33, tzinfo=timezone.utc))

    def test_parse_absolute_pst(self) -> None:
        now = datetime(2026, 5, 21, 8, 3, 39, tzinfo=timezone.utc)
        parsed = parse_reminder_request("on may 21 at 3pm PST to starship launch in 2 hours", now)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.text, "Starship launch in 2 hours")
        self.assertEqual(parsed.due_at, datetime(2026, 5, 21, 23, 0, 0, tzinfo=timezone.utc))

    def test_store_create_list_and_pop_due(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = JsonState(Path(tmp.name) / "state.json")
        current = datetime(2026, 2, 18, 23, 56, 30, tzinfo=timezone.utc)
        store = ReminderStore(state, now=lambda: current)
        self.assertEqual(
            store.handle("alice", "#c", "!remindme test in 20 seconds"),
            ["Created reminder 'Test' for 2026-02-18 23:56:50 GMT 🔔"],
        )
        listed = "\n".join(store.handle("alice", "#c", "!reminders") or [])
        self.assertIn("alice", listed)
        self.assertIn("Test", listed)
        current = datetime(2026, 2, 18, 23, 56, 51, tzinfo=timezone.utc)
        self.assertEqual(store.pop_due("alice", "#c"), ["⏰ Reminder for alice: Test"])
        self.assertEqual(store.handle("alice", "#c", "!reminders"), ["No reminders found."])


if __name__ == "__main__":
    unittest.main()
