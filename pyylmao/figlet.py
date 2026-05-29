from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Iterable


MAX_FIGLET_TEXT = 160


def is_figlet_command(text: str) -> bool:
    return parse_figlet_command(text) is not None


def render_figlet_command(text: str) -> list[str]:
    parsed = parse_figlet_command(text)
    if parsed is None:
        return []
    font, message = parsed
    if _unsafe_font_name(font):
        return [_font_error(font)]

    message = _normalize_message(message)
    for candidate in _font_candidates(font):
        rendered = _render_pyfiglet(candidate, message)
        if rendered is not None:
            return rendered
        rendered = _render_external_figlet(candidate, message)
        if rendered is not None:
            return rendered
        rendered = _render_builtin(candidate, message)
        if rendered is not None:
            return rendered
    return [_font_error(font)]


def parse_figlet_command(text: str) -> tuple[str, str] | None:
    match = re.match(
        r"^!(?:fg|f.glet)\s+(\S+)(?:\s+(.*))?$",
        text.strip(),
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    return match.group(1), match.group(2) or ""


def _normalize_message(message: str) -> str:
    message = message.replace("\r", " ").replace("\n", " ")
    return message[:MAX_FIGLET_TEXT]


def _unsafe_font_name(font: str) -> bool:
    return (
        not font
        or font.startswith("-")
        or "/" in font
        or "\\" in font
        or ".." in font
    )


def _font_candidates(font: str) -> Iterable[str]:
    lowered = font.lower()
    yield lowered
    underscored = lowered.replace("-", "_")
    if underscored != lowered:
        yield underscored


def _font_error(font: str) -> str:
    return f"Error: Font '{font}' not found."


def _render_pyfiglet(font: str, message: str) -> list[str] | None:
    try:
        import pyfiglet
    except ImportError:
        return None

    try:
        output = pyfiglet.figlet_format(message, font=font)
    except pyfiglet.FontNotFound:
        return None
    return output.rstrip("\n").splitlines()


def _render_external_figlet(font: str, message: str) -> list[str] | None:
    executable = shutil.which("figlet")
    if executable is None:
        return None
    completed = subprocess.run(
        [executable, "-f", font, message],
        check=False,
        capture_output=True,
        text=True,
        timeout=2,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.rstrip("\n").splitlines()


def _render_builtin(font: str, message: str) -> list[str] | None:
    if font != "calvin_s":
        return None
    return _render_calvin_s(message)


def _render_calvin_s(message: str) -> list[str]:
    if not message:
        return []
    lines = ["", "", ""]
    for char in message:
        glyph = CALVIN_S.get(char, ("", "", ""))
        for index, part in enumerate(glyph):
            lines[index] += part
    if not any(lines):
        return []
    return lines


CALVIN_S: dict[str, tuple[str, str, str]] = {
    "A": ("╔═╗", "╠═╣", "╩ ╩"),
    "B": ("╔╗ ", "╠╩╗", "╚═╝"),
    "C": ("╔═╗", "║  ", "╚═╝"),
    "D": ("╔╦╗", " ║║", "═╩╝"),
    "E": ("╔═╗", "║╣ ", "╚═╝"),
    "F": ("╔═╗", "╠╣ ", "╚  "),
    "G": ("╔═╗", "║ ╦", "╚═╝"),
    "H": ("╦ ╦", "╠═╣", "╩ ╩"),
    "I": ("╦", "║", "╩"),
    "J": (" ╦", " ║", "╚╝"),
    "K": ("╦╔═", "╠╩╗", "╩ ╩"),
    "L": ("╦  ", "║  ", "╩═╝"),
    "M": ("╔╦╗", "║║║", "╩ ╩"),
    "N": ("╔╗╔", "║║║", "╝╚╝"),
    "O": ("╔═╗", "║ ║", "╚═╝"),
    "P": ("╔═╗", "╠═╝", "╩  "),
    "Q": ("╔═╗ ", "║═╬╗", "╚═╝╚"),
    "R": ("╦═╗", "╠╦╝", "╩╚═"),
    "S": ("╔═╗", "╚═╗", "╚═╝"),
    "T": ("╔╦╗", " ║ ", " ╩ "),
    "U": ("╦ ╦", "║ ║", "╚═╝"),
    "V": ("╦  ╦", "╚╗╔╝", " ╚╝ "),
    "W": ("╦ ╦", "║║║", "╚╩╝"),
    "X": ("═╗ ╦", "╔╩╦╝", "╩ ╚═"),
    "Y": ("╦ ╦", "╚╦╝", " ╩ "),
    "Z": ("╔═╗", "╔═╝", "╚═╝"),
    "a": ("┌─┐", "├─┤", "┴ ┴"),
    "b": ("┌┐ ", "├┴┐", "└─┘"),
    "c": ("┌─┐", "│  ", "└─┘"),
    "d": ("┌┬┐", " ││", "─┴┘"),
    "e": ("┌─┐", "├┤ ", "└─┘"),
    "f": ("┌─┐", "├┤ ", "└  "),
    "g": ("┌─┐", "│ ┬", "└─┘"),
    "h": ("┬ ┬", "├─┤", "┴ ┴"),
    "i": ("┬", "│", "┴"),
    "j": (" ┬", " │", "└┘"),
    "k": ("┬┌─", "├┴┐", "┴ ┴"),
    "l": ("┬  ", "│  ", "┴─┘"),
    "m": ("┌┬┐", "│││", "┴ ┴"),
    "n": ("┌┐┌", "│││", "┘└┘"),
    "o": ("┌─┐", "│ │", "└─┘"),
    "p": ("┌─┐", "├─┘", "┴  "),
    "q": ("┌─┐ ", "│─┼┐", "└─┘└"),
    "r": ("┬─┐", "├┬┘", "┴└─"),
    "s": ("┌─┐", "└─┐", "└─┘"),
    "t": ("┌┬┐", " │ ", " ┴ "),
    "u": ("┬ ┬", "│ │", "└─┘"),
    "v": ("┬  ┬", "└┐┌┘", " └┘ "),
    "w": ("┬ ┬", "│││", "└┴┘"),
    "x": ("─┐ ┬", "┌┴┬┘", "┴ └─"),
    "y": ("┬ ┬", "└┬┘", " ┴ "),
    "z": ("┌─┐", "┌─┘", "└─┘"),
    "!": ("┬", "│", "o"),
    "?": ("┌─┐", " ┌┘", " o "),
    ".": (" ", " ", "o"),
    ",": (" ", " ", "┘"),
    "-": ("   ", "───", "   "),
    "_": ("    ", "    ", "────"),
    " ": ("  ", "  ", "  "),
}
