from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyylmao.chess_game import ChessStore, is_chess_command, render_board
from pyylmao.state import JsonState


class ChessGameTests(unittest.TestCase):
    def make_store(self) -> ChessStore:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return ChessStore(JsonState(Path(tmp.name) / "state.json"))

    def test_detects_chess_command(self) -> None:
        self.assertTrue(is_chess_command("!chess"))
        self.assertTrue(is_chess_command("!chess new"))
        self.assertTrue(is_chess_command("!chess bla new"))
        self.assertFalse(is_chess_command("!chessboard"))

    def test_usage_matches_logged_lines(self) -> None:
        store = self.make_store()
        self.assertEqual(
            store.handle("tinky", "!chess"),
            [
                "Usage: [gid] <command> [options]",
                "Commands: new, <move (e.g., e4, Nf3, or e2 e4)>, resign, draw",
            ],
        )

    def test_new_default_game_renders_logged_starting_board(self) -> None:
        store = self.make_store()
        lines = store.handle("malcom", "!chess new")
        self.assertEqual(lines[0], "New game 'default' created. White's move.")
        self.assertEqual(lines[1:], starting_board_lines())
        self.assertEqual(store.handle("malcom", "!chess new"), ["Error: Game with ID 'default' already exists."])

    def test_new_named_game(self) -> None:
        store = self.make_store()
        lines = store.handle("tinky", "!chess bla new")
        self.assertEqual(lines[0], "New game 'bla' created. White's move.")

    def test_moves_use_chess_rules_and_update_board(self) -> None:
        store = self.make_store()
        store.handle("white", "!chess new")
        lines = store.handle("white", "!chess e2 e4")
        self.assertEqual(lines[0], "white played e4. Black's move.")
        self.assertIn("║        ♙       ║ 4", lines)

        lines = store.handle("black", "!chess e5")
        self.assertEqual(lines[0], "black played e5. White's move.")
        self.assertIn("║        ♟       ║ 5", lines)

        lines = store.handle("white", "!chess nf3")
        self.assertEqual(lines[0], "white played Nf3. Black's move.")
        self.assertIn("║          ♘     ║ 3", lines)

    def test_non_player_draw_and_resign_errors_match_logs(self) -> None:
        store = self.make_store()
        store.handle("malcom", "!chess new")
        self.assertEqual(store.handle("Zodiac", "!chess draw"), ["Error: You are not a player in this game."])
        self.assertEqual(store.handle("Zodiac", "!chess resign"), ["Error: You are not a player in this game."])

    def test_unknown_game_and_illegal_move_errors(self) -> None:
        store = self.make_store()
        self.assertEqual(store.handle("alice", "!chess missing e4"), ["Error: Game with ID 'missing' does not exist."])
        store.handle("alice", "!chess new")
        self.assertEqual(store.handle("alice", "!chess e5"), ["Error: illegal move: e5"])


def starting_board_lines() -> list[str]:
    return [
        "╔════════════════╗",
        "║♜ ♞ ♝ ♛ ♚ ♝ ♞ ♜ ║ 8",
        "║♟ ♟ ♟ ♟ ♟ ♟ ♟ ♟ ║ 7",
        "║                ║ 6",
        "║                ║ 5",
        "║                ║ 4",
        "║                ║ 3",
        "║♙ ♙ ♙ ♙ ♙ ♙ ♙ ♙ ║ 2",
        "║♖ ♘ ♗ ♕ ♔ ♗ ♘ ♖ ║ 1",
        "╚════════════════╝",
        "  a b c d e f g h ",
    ]


class RenderBoardTests(unittest.TestCase):
    def test_render_board_exported_for_smoke(self) -> None:
        self.assertEqual(render_board.__name__, "render_board")
