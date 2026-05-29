from __future__ import annotations


class IRCFoldedCase(str):
    def __new__(cls, value: str = "") -> "IRCFoldedCase":
        return str.__new__(cls, lower(value))


def lower(value: str) -> str:
    return str(value).translate(str.maketrans("{}|^", "[]\\~")).lower()
