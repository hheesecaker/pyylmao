from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path

from .command_list import COMMANDS
from .state import JsonState


DEFAULT_TRIGGER_STATUS = {name: enabled for name, enabled, _pattern in COMMANDS}

TRIGGER_ALIASES = {
    "ai": "gpt",
    "cmds": "cmdlist",
    "fortune": "iching",
    "grok": "gpt",
    "reminder": "reminders",
    "remindme": "reminders",
    "stock": "stocks",
    "tool": "tools",
    "ud": "urbandict",
}


class TriggerStore:
    def __init__(
        self,
        state: JsonState,
        known_commands: Callable[[], Iterable[str]] | None = None,
    ):
        self.state = state
        self.known_commands = known_commands
        self.state.data.setdefault("trigger_enabled", {})

    def handle(self, text: str) -> list[str] | None:
        match = re.match(r"^!(enable|disable)\s+(\S+)\s*$", text.strip(), flags=re.IGNORECASE)
        if not match:
            if text.strip().lower() in {"!enable", "!disable"}:
                return ["Usage: !enable <trigger>"]
            return None
        action, raw_name = match.groups()
        display_name = self.display_name(raw_name)
        canonical_name = self.canonical_name(raw_name)
        if not self.exists(canonical_name):
            return [f"Trigger {display_name} does not exist"]
        enabled = action.lower() == "enable"
        if enabled and self.explicit_status(canonical_name) is True:
            return [f"Error: Command '{canonical_name}' is already enabled."]
        self.set(raw_name, enabled)
        status = "enabled" if enabled else "disabled"
        return [f"Trigger {display_name} is now {status}"]

    def enabled(self, name: str) -> bool:
        statuses = self.state.data["trigger_enabled"]
        canonical_name = self.canonical_name(name)
        if canonical_name in statuses:
            return bool(statuses[canonical_name])
        return DEFAULT_TRIGGER_STATUS.get(canonical_name, True)

    def set(self, name: str, enabled: bool) -> None:
        self.state.data["trigger_enabled"][self.canonical_name(name)] = enabled
        self.state.save()

    def explicit_status(self, name: str) -> bool | None:
        status = self.state.data["trigger_enabled"].get(self.canonical_name(name))
        return status if isinstance(status, bool) else None

    def exists(self, name: str) -> bool:
        return self.canonical_name(name) in self.trigger_names()

    def trigger_names(self) -> set[str]:
        if self.known_commands is not None:
            return {
                self.display_name(name)
                for name in self.known_commands()
                if self.display_name(name)
            }
        return default_trigger_names(self.state)

    @staticmethod
    def canonical_name(name: str) -> str:
        normalized = TriggerStore.display_name(name)
        return TRIGGER_ALIASES.get(normalized, normalized)

    @staticmethod
    def display_name(name: str) -> str:
        return name.strip().lower().lstrip("!@")


def default_trigger_names(state: JsonState) -> set[str]:
    names = {name for name, _, _ in COMMANDS}
    names.update(generated_trigger_names(state))
    return {TriggerStore.display_name(name) for name in names if TriggerStore.display_name(name)}


def generated_trigger_names(state: JsonState) -> set[str]:
    names: set[str] = set()
    root = state.data.setdefault("generated_commands", {})
    for name, entry in root.items():
        if not isinstance(entry, dict):
            continue
        path = Path(str(entry.get("path", "")))
        if path.exists() and path.is_file():
            names.add(str(name))
    generated_dir = state.path.parent / "generated_commands"
    if generated_dir.exists() and generated_dir.is_dir():
        names.update(path.stem for path in generated_dir.glob("*.py") if path.is_file())
    return names
