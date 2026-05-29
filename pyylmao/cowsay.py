from __future__ import annotations

import re
import textwrap


MAX_TEXT_WIDTH = 40


def is_cowsay_command(text: str) -> bool:
    return parse_cowsay_command(text) is not None


def render_cowsay_command(text: str) -> list[str]:
    parsed = parse_cowsay_command(text)
    if parsed is None:
        return []
    message = parsed
    wrapped = textwrap.wrap(message, width=MAX_TEXT_WIDTH) or [""]
    width = max(len(line) for line in wrapped)
    return render_bubble(wrapped, width) + COW


def parse_cowsay_command(text: str) -> str | None:
    match = re.match(r"^!cowsay(?::\S+)?\s+(.+)$", text.strip(), flags=re.DOTALL)
    if not match:
        return None
    return " ".join(match.group(1).split())


def render_bubble(lines: list[str], width: int) -> list[str]:
    top = " " + "_" * (width + 2)
    bottom = " " + "-" * (width + 2)
    if len(lines) == 1:
        return [top, f"< {lines[0].ljust(width)} >", bottom]

    out = [top]
    for index, line in enumerate(lines):
        padded = line.ljust(width)
        if index == 0:
            out.append(f"/ {padded} \\")
        elif index == len(lines) - 1:
            out.append(f"\\ {padded} /")
        else:
            out.append(f"| {padded} |")
    out.append(bottom)
    return out


COW = [
    r"        \   ^__^",
    r"         \  (oo)\_______",
    r"            (__)\       )\/\\",
    r"                ||----w |",
    r"                ||     ||",
]
