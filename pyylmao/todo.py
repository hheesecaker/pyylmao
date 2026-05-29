from __future__ import annotations

from .state import JsonState


class TodoStore:
    def __init__(self, state: JsonState):
        self.state = state
        self.state.data.setdefault("todos", {})

    def handle(self, nick: str, text: str) -> list[str] | None:
        stripped = text.strip()
        if not is_todo_command(stripped):
            return None
        task = stripped[len("!todo") :].strip()
        if task:
            self.todos_for(nick).append(task)
            self.state.save()
        return self.render(nick)

    def todos_for(self, nick: str) -> list[str]:
        todos = self.state.data["todos"]
        return todos.setdefault(nick, [])

    def render(self, nick: str) -> list[str]:
        lines = [f"{nick}'s Todos"]
        for index, task in enumerate(self.todos_for(nick), start=1):
            lines.append(f"{index}. ● {task}")
        return lines


def is_todo_command(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered == "!todo" or lowered.startswith("!todo ")
