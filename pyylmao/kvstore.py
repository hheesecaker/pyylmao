from __future__ import annotations

import json
import re
import ast
from dataclasses import dataclass
from typing import Any

from .state import JsonState


DEFAULT_KV = {
    "md2irc": {
        "options": {
            "use_figlet": True,
        }
    },
    "commands": {
        "gpt": {
            "_default": {
                "system": [
                    "Be concise, answer simple questions with simple answer",
                    "Err on the side of shorter responses, produce longer responses if asked to or if it's implied that you should do so",
                    "Respond with your response to the user only, do not include any other text",
                    "Make use of inline markdown formatting whenever appropriate",
                    "If your response includes code, format it as a markdown code block with the appropriate language string",
                    "Do not use any kind of (La)TeX notation, render using unicode symbols instead",
                    "Render exponents using unicode superscript numerals instead of X^Y notation",
                    "Do not include IRC nickname tags in your response",
                    "DO NOT prepend your message with your nickname in pointy brackets",
                ]
            }
        }
    },
}


@dataclass(frozen=True)
class KVCommand:
    action: str
    path: str
    value: str = ""
    flags: frozenset[str] = frozenset()


class KVStore:
    def __init__(self, state: JsonState):
        self.state = state
        self.root = state.data.setdefault("kvstore", {})
        merge_defaults(self.root, DEFAULT_KV)

    def handle(self, text: str) -> list[str] | None:
        command = parse_kv_command(text)
        if command is None:
            return None
        if command.action == "get":
            return self.get(command.path, command.flags)
        if command.action == "set":
            return self.set(command.path, parse_value(command.value))
        if command.action == "set_stats":
            return self.set(command.path, parse_value(command.value), stats=True)
        if command.action == "query":
            return self.query(command.path)
        if command.action == "append":
            return self.append(command.path, parse_value(command.value))
        if command.action == "append_stats":
            return self.append(command.path, parse_value(command.value), stats=True)
        if command.action == "del":
            return self.delete(command.path)
        if command.action == "info":
            return self.info()
        if command.action == "modes":
            return self.modes()
        if command.action:
            return [
                "unknown error, "
                f"op={command.action} "
                f"args={repr([command.action, command.path, command.value])}"
            ]
        return ["Usage: !kv <get|set|query> <path> [value]"]

    def get(self, path: str, flags: frozenset[str] = frozenset()) -> list[str]:
        found, value = get_path(self.root, split_path(path))
        if not found:
            return [f"{path} is not set"]
        if "json" in flags:
            return json.dumps(value, ensure_ascii=False, indent=2).splitlines()
        if "raw" in flags:
            return [repr(value)]
        if isinstance(value, (dict, list)):
            return render_tree(value)
        return [format_scalar(value)]

    def set(self, path: str, value: Any, stats: bool = False) -> list[str]:
        set_path(self.root, split_path(path), value)
        self.state.save()
        return [f"Set {path} to:", *render_tree({"value": value})]

    def append(self, path: str, value: Any, stats: bool = False) -> list[str]:
        parts = split_path(path)
        found, current = get_path(self.root, parts)
        if not found:
            set_path(self.root, parts, [])
            found, current = get_path(self.root, parts)
        if not isinstance(current, list):
            return [f"{path} is not a list"]
        current.append(value)
        self.state.save()
        if stats:
            return [f"Appended to {path}. New value:", *render_tree(current)]
        return ["None"]

    def delete(self, path: str) -> list[str]:
        deleted = delete_path(self.root, split_path(path))
        if deleted:
            self.state.save()
            return [f"Deleted {path}"]
        return [f"{path} is not set"]

    def query(self, expression: str) -> list[str]:
        path, _, op = expression.partition("|")
        path = path.strip()
        if re.search(r"\.\[\s*-?\d*\s*:", path):
            return [format_jq_slice_syntax_error(path)]
        syntax_error = format_logged_jq_query_syntax_error(path, op)
        if syntax_error:
            return [syntax_error]
        if path == "to_entries[]":
            return render_tree(to_entries(self.root))
        if path and not path.startswith(".") and not op:
            literal_found, literal_value = parse_query_literal(path)
            if literal_found:
                return render_tree({"value": literal_value})
        if path and not path.startswith("."):
            return ["Query returned no results"]
        found, value = get_path(self.root, split_path(path))
        if op == "keys" and (not found or value is None):
            return [format_jq_null_keys_error()]
        if not found:
            return ["Query returned no results"]
        if op == "keys":
            if isinstance(value, dict):
                value = list(value.keys())
            elif isinstance(value, list):
                value = list(range(len(value)))
            else:
                value = []
            return render_tree(value)
        if op == "length":
            try:
                value = len(value)
            except TypeError:
                value = 0
            return ["root", f"└── value: {format_scalar(value)}"]
        if op:
            return [f"Unsupported query operator: {op}"]
        if isinstance(value, (dict, list)):
            return render_tree(value)
        return [format_scalar(value)]

    def info(self) -> list[str]:
        return [
            "Backend: sqlite v0.0.0",
            f"Database: {self.state.path}.db",
            "",
        ]

    def modes(self) -> list[str]:
        return ["Modes: get, set, query, append, del, info"]


def is_kv_command(text: str) -> bool:
    return parse_kv_command(text) is not None


def parse_kv_command(text: str) -> KVCommand | None:
    tokens = text.strip().split()
    if not tokens or tokens[0].lower() != "!kv":
        return None
    rest = text.strip()[len(tokens[0]) :].strip()
    leading_flags, rest = consume_flags(rest)
    if not rest:
        return KVCommand(action="", path="", flags=leading_flags)
    action, _, rest = rest.partition(" ")
    action = action.lower()
    if action == "raw":
        inline_flags, rest = consume_flags(rest.strip())
        path, trailing_flags = strip_trailing_flags(rest.strip())
        return KVCommand(action="get", path=path, flags=leading_flags | inline_flags | trailing_flags | {action})
    if action in {"info", "modes"}:
        return KVCommand(action=action, path="", flags=leading_flags)
    if action not in {"get", "set", "query", "append", "del"}:
        path, value = split_path_and_value(rest.strip(), "set")
        return KVCommand(action=action, path=path, value=value, flags=leading_flags)
    inline_flags, rest = consume_flags(rest.strip())
    flags = leading_flags | inline_flags
    path, value = split_path_and_value(rest.strip(), action)
    value, trailing_flags = strip_trailing_flags(value)
    flags = flags | trailing_flags
    if "stats" in flags and action in {"set", "append"}:
        action = f"{action}_stats"
    return KVCommand(action=action, path=path, value=value, flags=flags)


def consume_flags(text: str) -> tuple[frozenset[str], str]:
    flags: set[str] = set()
    rest = text.strip()
    while rest.startswith("+"):
        token, _, remainder = rest.partition(" ")
        flag = token[1:].lower()
        if not flag:
            break
        flags.add(flag)
        rest = remainder.strip()
    return frozenset(flags), rest


def split_path_and_value(rest: str, action: str) -> tuple[str, str]:
    if action in {"get", "query", "del"}:
        return rest, ""
    path, _, value = rest.partition(" ")
    return path, value


def strip_trailing_flags(value: str) -> tuple[str, frozenset[str]]:
    flags: set[str] = set()
    rest = value.strip()
    while True:
        match = re.search(r"\s+\+([A-Za-z0-9_]+)\s*$", rest)
        if not match:
            return rest, frozenset(flags)
        flags.add(match.group(1).lower())
        rest = rest[: match.start()].strip()


def split_path(path: str) -> list[str]:
    stripped = path.strip()
    parts: list[str] = []
    index = 0
    while index < len(stripped):
        char = stripped[index]
        if char == ".":
            index += 1
            continue
        if char in {'"', "'"}:
            quote = char
            index += 1
            value = []
            while index < len(stripped):
                if stripped[index] == "\\" and index + 1 < len(stripped):
                    value.append(stripped[index + 1])
                    index += 2
                    continue
                if stripped[index] == quote:
                    index += 1
                    break
                value.append(stripped[index])
                index += 1
            parts.append("".join(value))
            continue
        if char == "[":
            end = stripped.find("]", index + 1)
            if end == -1:
                parts.append(stripped[index + 1 :])
                break
            parts.append(stripped[index + 1 : end].strip("'\""))
            index = end + 1
            continue
        start = index
        while index < len(stripped) and stripped[index] not in ".[":
            index += 1
        part = stripped[start:index]
        if part:
            parts.append(part)
    return parts


def get_path(root: Any, path: list[str]) -> tuple[bool, Any]:
    current = root
    for part in path:
        if isinstance(current, dict):
            if part not in current:
                return False, None
            current = current[part]
        elif isinstance(current, list):
            if ":" in part:
                list_slice = parse_list_slice(part)
                if list_slice is None:
                    return False, None
                current = current[list_slice]
                continue
            index = parse_list_index(part)
            if index is None:
                return False, None
            if index < 0:
                index += len(current)
            if index < 0 or index >= len(current):
                return False, None
            current = current[index]
        else:
            return False, None
    return True, current


def set_path(root: dict[str, Any], path: list[str], value: Any) -> None:
    if not path:
        return
    current: Any = root
    for index, part in enumerate(path[:-1]):
        next_part = path[index + 1]
        if isinstance(current, dict):
            if part not in current or not isinstance(current[part], (dict, list)):
                current[part] = [] if next_part.isdigit() else {}
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            list_index = int(part)
            while len(current) <= list_index:
                current.append([] if next_part.isdigit() else {})
            if not isinstance(current[list_index], (dict, list)):
                current[list_index] = [] if next_part.isdigit() else {}
            current = current[list_index]
        else:
            return
    last = path[-1]
    if isinstance(current, dict):
        current[last] = value
    elif isinstance(current, list) and last.isdigit():
        list_index = int(last)
        while len(current) <= list_index:
            current.append(None)
        current[list_index] = value


def delete_path(root: Any, path: list[str]) -> bool:
    if not path:
        return False
    found, parent = get_path(root, path[:-1])
    if not found:
        return False
    last = path[-1]
    if isinstance(parent, dict) and last in parent:
        del parent[last]
        return True
    if isinstance(parent, list) and last.isdigit():
        index = int(last)
        if index < len(parent):
            parent.pop(index)
            return True
    return False


def parse_value(raw: str) -> Any:
    stripped = raw.strip()
    if not stripped:
        return ""
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    if stripped.casefold() == "true":
        return True
    if stripped.casefold() == "false":
        return False
    if stripped.casefold() == "null":
        return None
    return stripped


def parse_query_literal(raw: str) -> tuple[bool, Any]:
    stripped = raw.strip()
    if not stripped:
        return False, None
    for loader in (json.loads, ast.literal_eval):
        try:
            return True, loader(stripped)
        except (json.JSONDecodeError, ValueError, SyntaxError):
            pass
    return False, None


def render_tree(value: Any) -> list[str]:
    lines = ["root"]
    children = list_children(value)
    for index, (label, child) in enumerate(children):
        last = index == len(children) - 1
        render_node(lines, label, child, "", last)
    return lines


def to_entries(value: Any) -> list[dict[str, Any]] | None:
    if isinstance(value, dict):
        return [{"key": key, "value": item} for key, item in value.items()]
    if isinstance(value, list):
        return [{"key": index, "value": item} for index, item in enumerate(value)]
    return None


def render_node(lines: list[str], label: str, value: Any, prefix: str, last: bool) -> None:
    branch = "└── " if last else "├── "
    if isinstance(value, (dict, list)):
        children = list_children(value)
        if not children:
            return
        lines.append(f"{prefix}{branch}{label}")
        child_prefix = prefix + ("   " if last else "│  ")
        for index, (child_label, child_value) in enumerate(children):
            render_node(lines, child_label, child_value, child_prefix, index == len(children) - 1)
    else:
        lines.append(f"{prefix}{branch}{label}: {format_scalar(value, quote_strings=True)}")


def list_children(value: Any) -> list[tuple[str, Any]]:
    if isinstance(value, list):
        return [(f"[{index}]", item) for index, item in enumerate(value)]
    if isinstance(value, dict):
        return [(str(key), value[key]) for key in sorted(value)]
    return []


def format_scalar(value: Any, quote_strings: bool = False) -> str:
    if quote_strings:
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "True" if value else "False"
    if value is None:
        return "null"
    return str(value)


def parse_list_index(part: str) -> int | None:
    if re.fullmatch(r"-?\d+", part):
        return int(part)
    return None


def parse_list_slice(part: str) -> slice | None:
    match = re.fullmatch(r"\s*(-?\d*)\s*:\s*(-?\d*)\s*", part)
    if not match:
        return None
    start_raw, stop_raw = match.groups()
    start = int(start_raw) if start_raw not in {"", "-"} else None
    stop = int(stop_raw) if stop_raw not in {"", "-"} else None
    return slice(start, stop)


def format_jq_slice_syntax_error(path: str) -> str:
    column = path.find(".[")
    if column == -1:
        column = len(path)
    colon = path.find(":", column)
    if colon != -1:
        column = colon
    caret = " " * (column + 4) + "^"
    message = (
        "jq: error: syntax error, unexpected ':', expecting '|' or ',' or ']' "
        f"at <top-level>, line 1, column {column + 1}:\n"
        f"    {path} \n"
        f"{caret}\n"
        "jq: 1 compile error"
    )
    return f"query error: {ValueError(message)!r}"


def format_logged_jq_query_syntax_error(path: str, op: str) -> str | None:
    expression = f"{path}|{op}" if op else path
    index = 0
    while index < len(path):
        char = path[index]
        if char == '"':
            index = skip_quoted(path, index, '"')
            continue
        if char == "'":
            return format_jq_invalid_character_error(expression, index, bracket_key=False)
        if char == "[":
            quote_index = next_nonspace_index(path, index + 1)
            if quote_index < len(path) and path[quote_index] == "'":
                return format_jq_invalid_character_error(expression, quote_index, bracket_key=True)
            index = skip_bracket(path, index)
            continue
        if char == "#":
            return format_jq_unquoted_hash_error(expression)
        if char == "-":
            name_match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", path[index + 1 :])
            if name_match:
                name = name_match.group(0)
                return format_jq_undefined_name_error(expression, name, index + 1)
        index += 1
    return None


def skip_quoted(text: str, start: int, quote: str) -> int:
    index = start + 1
    while index < len(text):
        if text[index] == "\\" and index + 1 < len(text):
            index += 2
            continue
        if text[index] == quote:
            return index + 1
        index += 1
    return index


def next_nonspace_index(text: str, start: int) -> int:
    index = start
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def skip_bracket(text: str, start: int) -> int:
    index = start + 1
    while index < len(text):
        if text[index] == '"':
            index = skip_quoted(text, index, '"')
            continue
        if text[index] == "]":
            return index + 1
        index += 1
    return index


def format_jq_invalid_character_error(expression: str, column: int, bracket_key: bool) -> str:
    expecting = "" if bracket_key else ", expecting FORMAT or QQSTRING_START or '['"
    message = (
        f"jq: error: syntax error, unexpected INVALID_CHARACTER{expecting} "
        f"at <top-level>, line 1, column {column + 1}:\n"
        f"    {expression}\n"
        f"{' ' * (column + 4)}^\n"
        "jq: 1 compile error"
    )
    return f"query error: {ValueError(message)!r}"


def format_jq_unquoted_hash_error(expression: str) -> str:
    column = max(len(expression) - 1, 0)
    message = (
        "jq: error: syntax error, unexpected end of file, expecting FORMAT or QQSTRING_START or '[' "
        f"at <top-level>, line 1, column {column + 1}:\n"
        f"    {expression}\n"
        f"{' ' * (column + 4)}^\n"
        "jq: 1 compile error"
    )
    return f"query error: {ValueError(message)!r}"


def format_jq_undefined_name_error(expression: str, name: str, column: int) -> str:
    message = (
        f"jq: error: {name}/0 is not defined at <top-level>, line 1, column {column + 1}:\n"
        f"    {expression} \n"
        f"{' ' * (column + 4)}{'^' * len(name)}\n"
        "jq: 1 compile error"
    )
    return f"query error: {ValueError(message)!r}"


def format_jq_null_keys_error() -> str:
    return "query error: ValueError('null (null) has no keys')"


def merge_defaults(target: dict[str, Any], defaults: dict[str, Any]) -> None:
    for key, value in defaults.items():
        if key not in target:
            target[key] = json.loads(json.dumps(value))
        elif isinstance(target[key], dict) and isinstance(value, dict):
            merge_defaults(target[key], value)
