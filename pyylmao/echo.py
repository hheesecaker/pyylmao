from __future__ import annotations

import html
import re


def is_echo_command(text: str) -> bool:
    stripped = text.strip()
    return stripped.lower() == "!echo" or stripped.lower().startswith("!echo ")


def render_echo_command(text: str) -> list[str]:
    if not is_echo_command(text):
        return []
    body = text.strip()[len("!echo") :].lstrip()
    if not body:
        return ["Usage: !echo <markdown>"]
    expanded = body.replace("\\n", "\n")
    rendered = render_echo_text(expanded)
    return rendered + ["", ""]


def render_echo_text(text: str) -> list[str]:
    lines = text.splitlines()
    quote_mode = bool(lines and lines[0].lstrip().startswith(">"))
    out: list[str] = []
    for line in lines:
        if quote_mode:
            out.append(render_quote_line(line))
        else:
            out.append(render_inline_markdown(line))
    return out or [""]


def render_quote_line(line: str) -> str:
    stripped = line.lstrip()
    if stripped.startswith(">"):
        stripped = stripped[1:]
        if stripped.startswith(" "):
            stripped = stripped[1:]
    if not stripped:
        return ""
    return "┃ " + render_inline_markdown(stripped)


def render_inline_markdown(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"</?(?:b|strong|i|em|u)>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    return text
