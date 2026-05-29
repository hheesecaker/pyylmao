from __future__ import annotations


def is_palette99_command(text: str) -> bool:
    return text.strip().lower() == "!palette99"


def render_palette99() -> list[str]:
    lines: list[str] = []
    for start in range(0, 99, 11):
        row = "".join(f"{number:02d}" for number in range(start, min(start + 11, 99)))
        lines.extend([row, ""])
    return lines
