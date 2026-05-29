from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyylmao.radio import RadioStore, is_radio_help_command, render_radio_help
from pyylmao.state import JsonState


class RadioTests(unittest.TestCase):
    def test_detects_help_command(self) -> None:
        self.assertTrue(is_radio_help_command("!help"))
        self.assertTrue(is_radio_help_command("  !HELP  "))
        self.assertFalse(is_radio_help_command("!help radio"))

    def test_renders_latest_logged_radio_help(self) -> None:
        self.assertEqual(render_radio_help()[0], "!np: Show the current track playing")
        self.assertIn("!playlist: List tracks in the active playlist", render_radio_help())
        self.assertEqual(
            render_radio_help()[-1],
            "+add <playlist> <link>: Append a track/album/artist/playlist",
        )

    def test_queued_empty_matches_logged_response(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = RadioStore(JsonState(Path(tmp.name) / "state.json"))

        self.assertEqual(store.handle("!queued"), ["Queue is empty."])

    def test_new_playlist_persists_and_matches_logged_spacing(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state_path = Path(tmp.name) / "state.json"
        store = RadioStore(JsonState(state_path))

        self.assertEqual(store.handle("!new memphis"), ["Playlist  memphis  successfully created!"])
        self.assertIn("memphis", RadioStore(JsonState(state_path)).state.data["radio"]["playlists"])


if __name__ == "__main__":
    unittest.main()
