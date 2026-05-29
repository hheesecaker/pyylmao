from __future__ import annotations

from typing import Iterable

from ...helpers import md2irc


class MDBuffer:
    def __init__(self, lines: Iterable[str] | None = None) -> None:
        self._lines = [str(line) for line in lines] if lines is not None else []

    def write(self, text: str) -> int:
        raw = str(text)
        self._lines.extend(raw.splitlines() or [raw])
        return len(raw)

    def writeline(self, text: str = "") -> None:
        self._lines.append(str(text))

    def extend(self, lines: Iterable[str]) -> None:
        self._lines.extend(str(line) for line in lines)

    def clear(self) -> None:
        self._lines.clear()

    def splitlines(self) -> list[str]:
        return list(self._lines)

    def getvalue(self) -> str:
        return "\n".join(self._lines)

    def render(self, **options) -> str:
        return render_markdown(self.getvalue(), **options)

    def __bool__(self) -> bool:
        return bool(self._lines)

    def __str__(self) -> str:
        return self.getvalue()


def render_markdown(text: str, **options) -> str:
    rendered = md2irc(str(text), **options)
    if isinstance(rendered, bytes):
        return rendered.decode("utf-8", errors="replace")
    return str(rendered)


def render_lines(text: str, **options) -> list[str]:
    return render_markdown(text, **options).splitlines()


__all__ = ["MDBuffer", "render_lines", "render_markdown"]
