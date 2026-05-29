from __future__ import annotations

from typing import Any, Callable

from ..mdcat import render_markdown_document


def md2irc(
    text: Any,
    output_fn: Callable[[str], Any] | None = None,
    **_: Any,
) -> bytes:
    """Render markdown-ish text to IRC-formatted UTF-8 bytes.

    Historical generated commands used both `md2irc(text).decode("utf-8")`
    and `md2irc(text, output_fn=print, **options)`.
    """
    lines = render_markdown_document(str(text))
    if output_fn is not None:
        for line in lines:
            output_fn(line)
    return "\n".join(lines).encode("utf-8")
