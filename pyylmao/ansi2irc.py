from __future__ import annotations

import re
import urllib.request
from dataclasses import dataclass
from typing import Callable


ANSI2IRC_RE = re.compile(r"^!(ansi2irc|irc2ansi)\s+(https?://\S+)$", re.IGNORECASE)
CSI_RE = re.compile(r"\x1b\[([0-9;?]*)([A-Za-z])")
IRC_COLOR_RE = re.compile(r"\x03(\d{1,2})?(?:,(\d{1,2}))?")
RESET_IRC = "\x0f"

ANSI_TO_IRC = {
    30: 1,
    31: 5,
    32: 3,
    33: 7,
    34: 2,
    35: 6,
    36: 10,
    37: 15,
    90: 14,
    91: 4,
    92: 9,
    93: 8,
    94: 12,
    95: 13,
    96: 11,
    97: 0,
}
IRC_TO_ANSI = {
    0: 97,
    1: 30,
    2: 34,
    3: 32,
    4: 91,
    5: 31,
    6: 35,
    7: 33,
    8: 93,
    9: 92,
    10: 36,
    11: 96,
    12: 94,
    13: 95,
    14: 90,
    15: 37,
}


class Ansi2IRCError(ValueError):
    pass


@dataclass
class Cell:
    char: str = " "
    fg: int | None = None
    bg: int | None = None


def is_ansi2irc_command(text: str) -> bool:
    return bool(ANSI2IRC_RE.match(text.strip()))


def render_ansi2irc_command(
    text: str,
    fetcher: Callable[[str], bytes] | None = None,
) -> list[str]:
    match = ANSI2IRC_RE.match(text.strip())
    if match is None:
        raise Ansi2IRCError("Usage: !ansi2irc <url> or !irc2ansi <url>")
    command = match.group(1).lower()
    url = match.group(2)
    data = (fetcher or fetch_url_bytes)(url)
    if len(data) > 1_000_000:
        raise Ansi2IRCError("ansi2irc input too large")

    if command == "irc2ansi":
        source = data.decode("utf-8", errors="replace")
        return bound_output(["IRC→ANSI (utf-8 detected):", *irc_to_ansi_text(source).splitlines()])

    cleaned = strip_sauce(data)
    encoding = detect_ansi_encoding(cleaned)
    source = cleaned.decode(encoding, errors="replace")
    if has_irc_controls(source) and not has_ansi_controls(source):
        return bound_output([f"IRC→ANSI ({encoding} detected):", *irc_to_ansi_text(source).splitlines()])
    converted = ansi_to_irc_text(source)
    return bound_output([f"ANSI→IRC ({encoding} detected):", *converted.splitlines()])


def fetch_url_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "pyylmao/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.read(1_000_001)
    except OSError as exc:
        raise Ansi2IRCError(f"ansi2irc fetch failed: {exc}") from exc


def strip_sauce(data: bytes) -> bytes:
    value = data
    if len(value) >= 128 and value[-128:-121] == b"SAUCE00":
        value = value[:-128]
    value = value.rstrip(b"\x00")
    return value.rstrip(b"\x1a\r\n")


def detect_ansi_encoding(data: bytes) -> str:
    if not data:
        return "utf-8"
    high = sum(byte >= 0x80 for byte in data)
    cp437_art = sum(byte in set(range(0xB0, 0xE0)) for byte in data)
    c1_controls = sum(0x80 <= byte <= 0x9F for byte in data)
    try:
        decoded = data.decode("utf-8")
    except UnicodeDecodeError:
        return "cp437"
    mojibake = sum(decoded.count(char) for char in "ÜÛÝÞß²±°")
    if c1_controls >= 2 or cp437_art >= 3 or mojibake >= 3:
        return "cp437"
    if high / max(1, len(data)) > 0.25 and cp437_art:
        return "cp437"
    return "utf-8"


def has_ansi_controls(text: str) -> bool:
    return "\x1b[" in text


def has_irc_controls(text: str) -> bool:
    return any(code in text for code in ("\x03", "\x02", "\x0f", "\x16", "\x1d", "\x1f"))


def ansi_to_irc_text(text: str, width: int = 80, max_rows: int = 240) -> str:
    screen: list[list[Cell]] = []
    x = 0
    y = 0
    fg: int | None = None
    bg: int | None = None
    bold = False

    def ensure(row: int, col: int) -> None:
        while len(screen) <= row:
            screen.append([])
        while len(screen[row]) <= col:
            screen[row].append(Cell())

    def put(char: str) -> None:
        nonlocal x, y
        if y >= max_rows:
            return
        ensure(y, x)
        screen[y][x] = Cell(char, fg, bg)
        x += 1
        if width > 0 and x >= width:
            x = 0
            y += 1

    pos = 0
    while pos < len(text):
        char = text[pos]
        if char == "\x1b":
            match = CSI_RE.match(text, pos)
            if match:
                params = parse_csi_params(match.group(1))
                command = match.group(2)
                if command == "m":
                    fg, bg, bold = apply_sgr(params, fg, bg, bold)
                elif command in {"H", "f"}:
                    row = (params[0] if params else 1) - 1
                    col = (params[1] if len(params) > 1 else 1) - 1
                    y = max(0, min(max_rows - 1, row))
                    x = max(0, col)
                elif command == "A":
                    y = max(0, y - (params[0] if params else 1))
                elif command == "B":
                    y = min(max_rows - 1, y + (params[0] if params else 1))
                elif command == "C":
                    x += params[0] if params else 1
                elif command == "D":
                    x = max(0, x - (params[0] if params else 1))
                elif command == "J":
                    if not params or params[0] in {2, 3}:
                        screen.clear()
                        x = y = 0
                elif command == "K":
                    if y < len(screen):
                        screen[y] = screen[y][:x]
                pos = match.end()
                continue
            pos += 1
            continue
        if char == "\r":
            x = 0
        elif char == "\n":
            y += 1
            x = 0
        elif char == "\t":
            for _ in range(8 - (x % 8)):
                put(" ")
        elif ord(char) >= 32:
            put(char)
        pos += 1

    lines = [render_row(row).rstrip() for row in screen]
    return "\n".join(line for line in lines if line.strip())


def parse_csi_params(value: str) -> list[int]:
    if not value:
        return []
    params = []
    for part in value.replace("?", "").split(";"):
        if not part:
            params.append(0)
            continue
        try:
            params.append(int(part))
        except ValueError:
            params.append(0)
    return params


def apply_sgr(
    params: list[int],
    fg: int | None,
    bg: int | None,
    bold: bool,
) -> tuple[int | None, int | None, bool]:
    if not params:
        params = [0]
    for param in params:
        if param == 0:
            fg = bg = None
            bold = False
        elif param == 1:
            bold = True
        elif param == 22:
            bold = False
        elif 30 <= param <= 37 or 90 <= param <= 97:
            fg = ANSI_TO_IRC.get(param)
        elif 40 <= param <= 47:
            bg = ANSI_TO_IRC.get(param - 10)
        elif 100 <= param <= 107:
            bg = ANSI_TO_IRC.get(param - 10)
        elif param == 39:
            fg = None
        elif param == 49:
            bg = None
    if bold and fg in {1, 5, 3, 7, 2, 6, 10, 15}:
        fg = {
            1: 14,
            5: 4,
            3: 9,
            7: 8,
            2: 12,
            6: 13,
            10: 11,
            15: 0,
        }.get(fg, fg)
    return fg, bg, bold


def render_row(row: list[Cell]) -> str:
    output: list[str] = []
    fg: int | None = None
    bg: int | None = None
    for cell in row:
        if cell.fg != fg or cell.bg != bg:
            output.append(irc_color(cell.fg, cell.bg))
            fg, bg = cell.fg, cell.bg
        output.append(cell.char)
    if fg is not None or bg is not None:
        output.append(RESET_IRC)
    return "".join(output)


def irc_color(fg: int | None, bg: int | None) -> str:
    if fg is None and bg is None:
        return "\x03"
    if fg is None:
        fg = 1
    if bg is None:
        return f"\x03{fg:02d}"
    return f"\x03{fg:02d},{bg:02d}"


def irc_to_ansi_text(text: str) -> str:
    output: list[str] = []
    pos = 0
    while pos < len(text):
        char = text[pos]
        if char == "\x03":
            match = IRC_COLOR_RE.match(text, pos)
            if match:
                fg = int(match.group(1)) if match.group(1) else None
                bg = int(match.group(2)) if match.group(2) else None
                codes = []
                if fg is not None:
                    codes.append(str(IRC_TO_ANSI.get(fg, 37)))
                if bg is not None:
                    codes.append(str(IRC_TO_ANSI.get(bg, 30) + 10))
                output.append(f"\x1b[{';'.join(codes) if codes else '0'}m")
                pos = match.end()
                continue
        if char == "\x0f":
            output.append("\x1b[0m")
        elif char == "\x02":
            output.append("\x1b[1m")
        elif char in {"\x16", "\x1d", "\x1f"}:
            pass
        else:
            output.append(char)
        pos += 1
    output.append("\x1b[0m")
    return "".join(output)


def bound_output(lines: list[str], max_lines: int = 120) -> list[str]:
    bounded = lines[:max_lines]
    if len(lines) > max_lines:
        bounded.append(f"... truncated {len(lines) - max_lines} lines")
    return bounded
