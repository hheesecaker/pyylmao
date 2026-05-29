from __future__ import annotations

import re

from .state import JsonState


class FilterStore:
    def __init__(self, state: JsonState):
        self.state = state
        self.state.data.setdefault("filters", [])

    def handle(self, text: str) -> list[str] | None:
        parts = text.strip().split(maxsplit=1)
        if not parts:
            return None
        command = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        if command == "!blist":
            return self.list()
        if command == "!add":
            return self.add(arg)
        if command == "!del":
            return self.delete(arg)
        return None

    def list(self) -> list[str]:
        filters = self.state.data["filters"]
        if not filters:
            return ["No tracked filters."]
        return [f"{idx}) {item}" for idx, item in enumerate(filters, start=1)]

    def patterns(self) -> list[str]:
        return list(self.state.data["filters"])

    def add(self, pattern: str) -> list[str]:
        pattern = pattern.strip()
        if not pattern:
            return ["Usage: !add <regex-or-term>"]
        try:
            re.compile(pattern)
        except re.error as exc:
            return [f"Invalid regex: {exc}"]
        filters = self.state.data["filters"]
        filters.append(pattern)
        self.state.save()
        return self.list()

    def delete(self, arg: str) -> list[str]:
        arg = arg.strip()
        filters = self.state.data["filters"]
        if not arg:
            return ["Usage: !del <number-or-pattern>"]
        if arg.isdigit():
            index = int(arg) - 1
            if index < 0 or index >= len(filters):
                return ["No filter at that index."]
            removed = filters.pop(index)
        else:
            try:
                filters.remove(arg)
            except ValueError:
                return ["No matching filter."]
        self.state.save()
        return self.list()
