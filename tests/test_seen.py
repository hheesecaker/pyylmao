from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyylmao.history_store import record_history
from pyylmao.seen import render_seen_command
from pyylmao.state import JsonState


class SeenCommandTests(unittest.TestCase):
    def make_state(self) -> JsonState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return JsonState(Path(tmp.name) / "state.json")

    def test_render_seen_command_matches_logged_success_shape(self) -> None:
        state = self.make_state()
        record_history(
            state,
            "#c",
            "malcom",
            "!seen malcom",
            ts=1766479443,
        )

        self.assertEqual(
            render_seen_command("!seen malcom", state, "#c", "someone"),
            ["malcom was last seen pon 2025-12-23 08:44:03 UTC saying: !seen malcom"],
        )

    def test_render_seen_command_matches_logged_missing_shape(self) -> None:
        state = self.make_state()

        self.assertEqual(
            render_seen_command("!seen ryan", state, "#c", "malcom"),
            ["User ryan not found in history."],
        )

    def test_render_seen_command_treats_current_sender_as_seen_now(self) -> None:
        state = self.make_state()

        self.assertEqual(
            render_seen_command("!seen malcom", state, "#c", "malcom", now=lambda: 1766479443),
            ["malcom was last seen pon 2025-12-23 08:44:03 UTC saying: !seen malcom"],
        )


if __name__ == "__main__":
    unittest.main()
