from __future__ import annotations

import re
from dataclasses import dataclass

import chess

from .formatting import clean_nick
from .state import JsonState


USAGE_LINES = [
    "Usage: [gid] <command> [options]",
    "Commands: new, <move (e.g., e4, Nf3, or e2 e4)>, resign, draw",
]

PIECES = {
    "r": "♜",
    "n": "♞",
    "b": "♝",
    "q": "♛",
    "k": "♚",
    "p": "♟",
    "R": "♖",
    "N": "♘",
    "B": "♗",
    "Q": "♕",
    "K": "♔",
    "P": "♙",
}


@dataclass(frozen=True)
class ChessCommand:
    gid: str
    command: str


class ChessStore:
    def __init__(self, state: JsonState):
        self.state = state
        self.state.data.setdefault("chess_games", {})

    def handle(self, nick: str, text: str) -> list[str] | None:
        parsed = parse_chess_command(text)
        if parsed is None:
            return None
        if parsed.command == "":
            return USAGE_LINES.copy()
        if parsed.command == "new":
            return self.new_game(parsed.gid, clean_nick(nick))
        if parsed.command == "draw":
            return self.player_only(parsed.gid, clean_nick(nick))
        if parsed.command == "resign":
            return self.resign(parsed.gid, clean_nick(nick))
        if parsed.command == "show":
            return self.show(parsed.gid)
        return self.move(parsed.gid, clean_nick(nick), parsed.command)

    def games(self) -> dict[str, dict[str, str | None]]:
        return self.state.data["chess_games"]

    def new_game(self, gid: str, nick: str) -> list[str]:
        if gid in self.games():
            return [f"Error: Game with ID '{gid}' already exists."]
        self.games()[gid] = {
            "fen": chess.STARTING_FEN,
            "white": nick,
            "black": None,
        }
        self.state.save()
        return [f"New game '{gid}' created. White's move.", *render_board(chess.Board())]

    def show(self, gid: str) -> list[str]:
        game = self.games().get(gid)
        if game is None:
            return [f"Error: Game with ID '{gid}' does not exist."]
        return render_board(chess.Board(str(game["fen"])))

    def player_only(self, gid: str, nick: str) -> list[str]:
        game = self.games().get(gid)
        if game is None:
            return [f"Error: Game with ID '{gid}' does not exist."]
        if nick not in {game.get("white"), game.get("black")}:
            return ["Error: You are not a player in this game."]
        return ["Draw offered."]

    def resign(self, gid: str, nick: str) -> list[str]:
        game = self.games().get(gid)
        if game is None:
            return [f"Error: Game with ID '{gid}' does not exist."]
        if nick not in {game.get("white"), game.get("black")}:
            return ["Error: You are not a player in this game."]
        winner = "Black" if game.get("white") == nick else "White"
        del self.games()[gid]
        self.state.save()
        return [f"{nick} resigns. {winner} wins."]

    def move(self, gid: str, nick: str, raw_move: str) -> list[str]:
        game = self.games().get(gid)
        if game is None:
            return [f"Error: Game with ID '{gid}' does not exist."]
        board = chess.Board(str(game["fen"]))
        color_key = "white" if board.turn == chess.WHITE else "black"
        player = game.get(color_key)
        if player is None:
            game[color_key] = nick
        elif player != nick:
            return [f"Error: It is {color_key}'s turn."]

        try:
            move = parse_move(board, raw_move)
        except ValueError as exc:
            return [f"Error: {exc}"]
        san = board.san(move)
        board.push(move)
        game["fen"] = board.fen()
        self.state.save()

        next_turn = "White" if board.turn == chess.WHITE else "Black"
        lines = [f"{nick} played {san}. {next_turn}'s move.", *render_board(board)]
        if board.is_checkmate():
            lines[0] = f"{nick} played {san}. Checkmate."
            del self.games()[gid]
            self.state.save()
        elif board.is_stalemate():
            lines[0] = f"{nick} played {san}. Stalemate."
            del self.games()[gid]
            self.state.save()
        return lines


def is_chess_command(text: str) -> bool:
    return parse_chess_command(text) is not None


def parse_chess_command(text: str) -> ChessCommand | None:
    match = re.match(r"^!chess(?:\s+(.*))?$", text.strip(), flags=re.IGNORECASE)
    if not match:
        return None
    rest = (match.group(1) or "").strip()
    if not rest:
        return ChessCommand("default", "")
    parts = rest.split(maxsplit=1)
    first = parts[0].lower()
    if first in {"new", "draw", "resign", "show"} or looks_like_move(rest):
        return ChessCommand("default", rest.lower() if first in {"new", "draw", "resign", "show"} else rest)
    if len(parts) == 1:
        return ChessCommand("default", rest)
    return ChessCommand(parts[0], parts[1].strip())


def looks_like_move(text: str) -> bool:
    return bool(re.match(r"^(?:[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|[a-h][1-8]\s+[a-h][1-8]|O-O(?:-O)?)$", text))


def parse_move(board: chess.Board, raw_move: str) -> chess.Move:
    candidate = raw_move.strip()
    spaced = re.match(r"^([a-h][1-8])\s+([a-h][1-8])$", candidate, flags=re.IGNORECASE)
    if spaced:
        candidate = "".join(spaced.groups())
    if candidate[:1] in {"k", "q", "r", "b", "n"}:
        candidate = candidate[0].upper() + candidate[1:]
    try:
        move = chess.Move.from_uci(candidate.lower())
        if move in board.legal_moves:
            return move
    except ValueError:
        pass
    try:
        return board.parse_san(candidate)
    except ValueError as exc:
        raise ValueError(f"illegal move: {raw_move}") from exc


def render_board(board: chess.Board) -> list[str]:
    lines = ["╔════════════════╗"]
    for rank in range(7, -1, -1):
        cells = []
        for file_index in range(8):
            piece = board.piece_at(chess.square(file_index, rank))
            cells.append((PIECES[piece.symbol()] if piece else " ") + " ")
        lines.append("║" + "".join(cells) + f"║ {rank + 1}")
    lines.extend(["╚════════════════╝", "  a b c d e f g h "])
    return lines
