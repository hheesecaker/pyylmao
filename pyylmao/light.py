from __future__ import annotations

import re


LIGHT_REPLY = "colour changed to    "


def is_light_command(text: str) -> bool:
    return parse_light_command(text) is not None


def render_light_command(text: str) -> list[str]:
    parsed = parse_light_command(text)
    if parsed is None:
        return []
    color, _brightness = parsed
    if color:
        return [LIGHT_REPLY]
    return []


def parse_light_command(text: str) -> tuple[str | None, int | None] | None:
    match = re.match(
        r"^!light ?([#a-zA-Z ]+)? ?(\d+)?$",
        text.strip(),
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    raw_color, raw_brightness = match.groups()
    color = raw_color.strip() if raw_color and raw_color.strip() else None
    brightness = int(raw_brightness) if raw_brightness is not None else None
    return color, brightness
