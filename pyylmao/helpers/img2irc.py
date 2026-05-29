from __future__ import annotations

from typing import Any

from ..img2irc import render_img2irc_command


def img2irc(url: str, **options: Any) -> str:
    """Render an image URL and return newline-joined IRC/ANSI output.

    The original helper accepted keyword arguments and delegated to an external
    img2irc binary. This wrapper maps the common logged options onto the
    reconstructed Python renderer and ignores unknown binary-only flags.
    """
    command = helper_command(str(url), options)
    return "\n".join(render_img2irc_command(command))


def helper_command(url: str, options: dict[str, Any]) -> str:
    parts = ["!img2irc", url]
    for key, value in options.items():
        normalized = str(key).strip().lower().replace("_", "-")
        if value in (None, "", False):
            continue
        if normalized in {"width", "w", "render", "contrast", "brightness", "saturation", "gamma"}:
            parts.extend([normalized, str(value)])
        elif normalized == "blocks":
            parts.extend(["blocks", comma_value(value)])
        elif normalized == "sharpen" and bool(value):
            parts.append("+sharpen")
        elif normalized in {"grayscale", "grey-scale", "greyscale"} and bool(value):
            parts.append("+grayscale")
    return " ".join(parts)


def comma_value(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        return ",".join(str(item) for item in value)
    return str(value)
