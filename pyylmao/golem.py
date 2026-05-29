from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import Any

from .state import JsonState


def parse_golem_control(text: str) -> str | None:
    stripped = text.strip()
    if not stripped.startswith("!>"):
        return None
    body = stripped[2:].strip()
    return body or ""


def is_golem_control_command(text: str) -> bool:
    return parse_golem_control(text) is not None


@dataclass
class GolemControlStore:
    state: JsonState

    def __post_init__(self) -> None:
        self.state.data.setdefault("golem_params", {})

    @property
    def params(self) -> dict[str, Any]:
        return self.state.data["golem_params"]

    def handle(self, text: str) -> list[str] | None:
        body = parse_golem_control(text)
        if body is None:
            return None
        if body == "clear":
            return ["* Context cleared *"]

        try:
            tokens = shlex.split(body)
        except ValueError as exc:
            return [f"Unknown command: {body}"]

        if not tokens:
            return ["Unknown command: "]

        changed = False
        for token in tokens:
            if token.startswith("-") and len(token) > 1 and "=" not in token:
                self.params.pop(token[1:], None)
                changed = True
                continue
            if "=" in token and not token.startswith("="):
                key, value = token.split("=", 1)
                if key:
                    self.params[key] = parse_param_value(value)
                    changed = True
                    continue
            return [f"Unknown command: {body}"]

        if changed:
            self.state.save()
            return [f"Parameters updated: {self.params!r}"]
        return [f"Unknown command: {body}"]


def parse_param_value(value: str) -> Any:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value
