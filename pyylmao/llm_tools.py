from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, unquote, urlparse
from urllib.request import Request, urlopen

from .command_list import COMMANDS
from .generated_commands import (
    GeneratedCommandStore,
    generated_command_source_path,
    safe_identifier as generated_safe_identifier,
)
from .gay import _base_url
from .history_store import BOT_NICK, history_items
from .state import JsonState
from .tools_table import tool_enabled


TOOL_ALIASES = {
    "list_artifact": "list_artifacts",
    "query_skill": "query_skills",
}


RAW_COMMAND_MODULES = {
    "@@": "router",
}


COMMAND_MODULES = {
    "ansi2irc": "ansi2irc",
    "ansi2irc2": "ansi2irc",
    "ascii": "ascii_art",
    "cmdlist": "command_list",
    "convo": "router",
    "cows": "cowsay",
    "cp": "cp",
    "drink": "bluesky",
    "eval": "eval_command",
    "fortune": "fortune",
    "forecast": "weather",
    "gpt": "router",
    "hf": "huggingface",
    "howsblair": "blair",
    "howsblair2": "blair",
    "iching": "fortune",
    "invite": "invite",
    "kv": "kvstore",
    "kv_append": "kv/backends/sqlite",
    "kv_delete": "kv/backends/sqlite",
    "kv_get": "kv/backends/sqlite",
    "kv_merge": "kv/backends/sqlite",
    "kv_query": "kv/backends/sqlite",
    "kv_set": "kv/backends/sqlite",
    "kvcontext": "kv/backends/sqlite",
    "kvresult": "kv/backends/sqlite",
    "lepro": "light",
    "link_title": "link_preview",
    "ligma": "ligma",
    "md2irc": "helpers/md2irc",
    "names": "history_store",
    "nostr": "nostr",
    "pheno": "phenoguessr",
    "phenoguessr": "phenoguessr",
    "pmall": "pmall",
    "poll_vote": "vote",
    "random": "random_command",
    "reminder": "reminders",
    "remindme": "reminders",
    "seen": "seen",
    "stock": "stocks",
    "test": "test_command",
    "teste": "test_command",
    "tools": "tools_table",
    "twitter": "twitter",
    "ud": "urbandict",
    "urban": "urbandict",
    "urbandict": "urbandict",
    "userlist": "history_store",
    "users": "history_store",
    "votes": "vote",
    "wsummary": "summary",
    "youtube": "link_preview",
    "yt": "summary",
    "ytsearch": "ytsearch",
    "ytsummary": "summary",
}


BUILTIN_SKILLS: dict[str, str] = {
    "KV": """# KV
Generated Python commands get a module-level `kv` helper scoped to `commands.<command_name>`.

Use `kv.get(path, default=...).expect(type)` to read JSON-compatible values, `kv.set(path, value)` to write values, `kv.append(path, value)` to append to a list, `kv.merge(path, dict_value)` to recursively merge dictionaries such as cached trivia entries, and `kv.delete(path)` to delete a path. Results are `KvResult` objects with `success()`, `failed()`, `expect()`, `unwrap()`, `json()`, and `to_dict()` helpers.

For ad hoc IRC use, `!kv get path`, `!kv set path value`, `!kv append path value`, `!kv del path`, `!kv info path`, `!kv modes`, and `!kv query .path|keys` operate on the shared JSON tree. Paths use dotted components and bracket/quoted keys. Values are parsed as JSON when possible, so `false`, `42`, `["a"]`, and `{"x":1}` become typed values.

Example:
```
count = kv.get("count", default=0).expect(int)
kv.set("count", count + 1)
print(count + 1)
```""",
    "img2irc": """# img2irc
`!img2irc <url> [width N] [render irc|ansi|ansi24]` fetches an image URL, resizes it, and renders colored block output for IRC.

Accepted forms include a bare numeric width (`!img2irc URL 45`), `width 45`, `render ansi24`, `+blocks`, `+sharpen`, `+grayscale`, `--contrast N`, `--brightness N`, `--saturation N`, and `--gamma N`. Width is clamped to 1..120 and output is bounded for IRC.

Generated commands can also use `from pyylmao.helpers import img2irc`; call `img2irc(url, width=72, render="ansi24", contrast=20)` and print the returned newline-separated output.

Use a publicly reachable URL. For local artifacts/images, save the file and serve it through the configured image-server or tunnel before calling `!img2irc`.""",
    "imghax": """# imghax
`!hax <url> [width] [img2irc options]` is the historical image-rendering alias. It routes through the `imghax` trigger but uses the same renderer and options as `!img2irc`.

Examples:
```
!hax https://example.test/a.png 45 --contrast 1.5
!hax https://example.test/a.png width 60 render ansi24 +blocks
```""",
    "md2irc": """# md2irc
Markdown-to-IRC rendering is available through `!mdcat <file>`, which reads a safe local markdown file from the configured mdcat directory and emits IRC-formatted lines.

The renderer handles headings, emphasis, links, quotes, bullet/numbered lists, inline code, fenced code, and pipe tables. It prints the mdcat options dict before rendered content, matching the historical command.

Generated commands can use `from pyylmao.helpers import md2irc`. `md2irc(text)` returns UTF-8 bytes, so use `md2irc(text).decode("utf-8")`, or call `md2irc(text, output_fn=print, **options)` to print rendered lines directly.

The shared KV tree also contains `md2irc.options` values used by older command-generation sessions, such as `md2irc.options.use_figlet`.""",
    "llm": """# llm
Use LLM tools to inspect existing commands, write generated commands, run debug code, and verify behavior before finalizing.

Important tools: `read_command` for reconstructed source, `write_command` for generated command artifacts, `revise_pattern` for trigger regexes, `run` for shell/debug execution, `get_chat_history` for channel context, `save_artifact`/`read_artifact`/`list_artifacts` for files, and `read_skill` for these built-in notes.

Generated command modules may use the modern `import llm; class Tool(llm.Toolbox): pattern = r"..."; def _onload(self): ...` API or the legacy `pattern = r"..."; def entrypoint(args, channel, nickname, username, hostname): ...` API. The runner also accepts older `run(bot, channel, sender, args)` and `command(bot, args)` callables. Printed stdout/stderr and returned strings/lists become IRC reply lines.

Generated commands can call `llm.get_model("openrouter/provider/model").prompt(text).text()` for a nested model request. Schema classes passed as `schema=...` are converted into a JSON-output hint. The logged Python `llm` shapes `system="..."`, `temperature=...` or `options={"temperature": ...}`, and image attachments via `llm.Attachment(url=..., type="image/png")` are supported.

`llm.get_tools()` returns an iterable/mapping-like inventory of available LLM tools. Each tool has `name`, `plugin`, and `enabled` attributes, and lookups such as `'write_command' in llm.get_tools()` and `llm.get_tools()['write_command']` work.""",
}

BUILTIN_SKILL_ALIASES: dict[str, str] = {
    "kv": "KV",
    "kvstore": "KV",
    "keyvalue": "KV",
    "key-value": "KV",
    "hax": "imghax",
    "mdcat": "md2irc",
}
BUILTIN_SKILL_ALIASES.update({name.casefold(): name for name in BUILTIN_SKILLS})


def builtin_skill_name(name: str) -> str | None:
    return BUILTIN_SKILL_ALIASES.get(str(name).strip().casefold())


class ToolExecutor(Protocol):
    def schemas(self) -> list[dict[str, Any]]:
        ...

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        ...


@dataclass(frozen=True)
class LLMToolContext:
    target: str
    history: tuple[tuple[str, str], ...]
    state: JsonState | None = None


class ToolResult(str):
    def __new__(cls, value: str, *, trace_label: str = "") -> "ToolResult":
        obj = str.__new__(cls, value)
        obj.trace_label = trace_label
        return obj


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str = ""


class LLMToolRegistry:
    def __init__(
        self,
        state: JsonState,
        source_root: Path | None = None,
        generated_dir: Path | None = None,
        artifact_dir: Path | None = None,
        package_timeout: int = 120,
        run_timeout: int = 30,
        raw_irc_sender: Any = None,
        command_runner: Any = None,
        web_searcher: Callable[[str, str], list[WebSearchResult]] | None = None,
    ):
        self.state = state
        self.source_root = source_root or Path(__file__).resolve().parent
        self.generated_dir = generated_dir or state.path.parent / "generated_commands"
        self.artifact_dir = artifact_dir or default_artifact_dir(state)
        self.package_timeout = package_timeout
        self.run_timeout = run_timeout
        self.raw_irc_sender = raw_irc_sender
        self.command_runner = command_runner
        self.web_searcher = web_searcher or default_web_search

    def bind(self, context: LLMToolContext) -> "BoundLLMTools":
        return BoundLLMTools(self, context)

    def schemas(self) -> list[dict[str, Any]]:
        schemas = [
            schema(
                "read_command",
                "Read the source for a reconstructed bot command by name, or omit name to list commands.",
                {"name": {"type": "string"}},
                [],
            ),
            schema(
                "write_command",
                (
                    "Write a generated command. Use code for executable Python and content only "
                    "for a short description. The name is optional when code contains an inferable "
                    "pattern like ^!command. Prefer class Tool(llm.Toolbox) with pattern and _onload(), "
                    "or legacy pattern plus entrypoint(args, channel, nickname, username, hostname). "
                    "Printed output and returned strings/lists become IRC replies."
                ),
                {
                    "name": {"type": "string", "description": "Generated command name, without .py."},
                    "content": {"type": "string", "description": "Optional human-readable description."},
                    "code": {"type": "string", "description": "Complete executable Python command module source."},
                    "pattern": {"type": "string", "description": "Python regex that triggers this command."},
                },
                [],
            ),
            schema(
                "revise_pattern",
                "Store or update the regex trigger pattern for a generated command.",
                {
                    "name": {"type": "string"},
                    "pattern": {"type": "string"},
                },
                ["name", "pattern"],
            ),
            schema(
                "install_packages",
                "Install Python packages with pip in the bot runtime.",
                {"packages": {"type": "array", "items": {"type": "string"}}},
                ["packages"],
            ),
            schema(
                "run",
                (
                    "Run a generated or reconstructed command by name with args. Prefer cmd_name "
                    "and args when testing bot commands; use command only for short shell/debug commands."
                ),
                {
                    "command": {"type": "string", "description": "Short shell command for low-level debugging."},
                    "cmd_name": {"type": "string", "description": "Generated or reconstructed command name to execute."},
                    "args": {"type": "string", "description": "Command args, as text or a Python/JSON list literal."},
                },
                [],
            ),
            schema(
                "get_chat_history",
                "Return recent persisted IRC chat history for the current channel.",
                {
                    "channel": {"type": "string"},
                    "max_lines": {"type": "string"},
                    "include_bot": {"type": "string"},
                },
                [],
            ),
            schema(
                "irc_command",
                "Record a raw IRC command requested by the model for command debugging.",
                {"command": {"type": "string"}},
                ["command"],
            ),
            schema(
                "channel_list",
                "List IRC channels known from persisted bot state.",
                {},
                [],
            ),
            schema(
                "get_channel_users",
                "List users known for a persisted IRC channel.",
                {"channel": {"type": "string"}},
                [],
            ),
            schema(
                "llm_version",
                "Return reconstructed LLM tool runtime version information.",
                {},
                [],
            ),
            schema(
                "llm_time",
                "Return current UTC time for command debugging.",
                {},
                [],
            ),
            schema(
                "eval",
                "Run a short Python snippet for command debugging.",
                {"code": {"type": "string"}},
                ["code"],
            ),
            schema(
                "read_skill",
                "Read a built-in or state-backed skill by name.",
                {"name": {"type": "string"}},
                ["name"],
            ),
            schema(
                "list_skills",
                "List built-in and state-backed skills.",
                {},
                [],
            ),
            schema(
                "create_skill",
                "Create or replace a state-backed skill.",
                {"name": {"type": "string"}, "content": {"type": "string"}},
                ["name", "content"],
            ),
            schema(
                "query_skills",
                "Search built-in and state-backed skill names and contents.",
                {"query": {"type": "string"}},
                ["query"],
            ),
            schema(
                "update_skill",
                "Update an existing state-backed skill.",
                {"name": {"type": "string"}, "content": {"type": "string"}},
                ["name", "content"],
            ),
            schema(
                "remember",
                "Store one or more memories.",
                {
                    "text": {"type": "string"},
                    "memories": {"type": "string"},
                },
                [],
            ),
            schema(
                "forget",
                "Forget memories matching text, key, or id.",
                {
                    "query": {"type": "string"},
                    "keys": {"type": "string"},
                },
                [],
            ),
            schema(
                "search_memories",
                "Search stored memories by plain text.",
                {"queries": {"type": "string"}},
                ["queries"],
            ),
            schema(
                "semantic_search",
                "Search the web for current external information. Profiles include instant, balanced, news, comprehensive, and web_search.",
                {
                    "query": {"type": "string"},
                    "phrases": {"type": "string"},
                    "profile": {"type": "string"},
                },
                [],
            ),
            schema(
                "save_artifact",
                "Save a text artifact and return a public URL when the asset server is configured.",
                {
                    "filename": {"type": "string"},
                    "contents": {"type": "string"},
                    "content": {"type": "string"},
                    "create_dirs": {"type": "string"},
                },
                [],
            ),
            schema(
                "read_artifact",
                "Read a text artifact from the bot artifact directory.",
                {"filename": {"type": "string"}},
                ["filename"],
            ),
            schema(
                "list_artifacts",
                "List files and directories in the bot artifact directory.",
                {"subdir": {"type": "string"}},
                [],
            ),
        ]
        static_names = {tool_schema["function"]["name"] for tool_schema in schemas}
        enabled_schemas = [
            tool_schema for tool_schema in schemas
            if tool_enabled(tool_schema["function"]["name"], self.state)
        ]
        return [*enabled_schemas, *self.command_tool_schemas(static_names)]

    def execute(self, context: LLMToolContext, name: str, arguments: dict[str, Any]) -> str:
        name = TOOL_ALIASES.get(str(name).strip(), name)
        if str(name).startswith("default_api:"):
            name = str(name).split(":", 1)[1]
        method = getattr(self, f"tool_{name}", None)
        if method is None:
            command_result = self.execute_command_tool(context, str(name), arguments)
            if command_result is not None:
                return command_result
            return f"Unknown tool: {name}"
        result = method(context, **arguments)
        if isinstance(result, ToolResult):
            return result
        return str(result)

    def command_tool_schemas(self, static_names: set[str]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen = set(static_names)
        if self.command_runner is not None:
            for name, _enabled, pattern in COMMANDS:
                if not valid_llm_tool_name(name) or name in seen:
                    continue
                if not self.command_trigger_enabled(name):
                    continue
                rows.append(command_tool_schema(name, pattern, "pyylmao_commands"))
                seen.add(name)
        for name, pattern in self.generated_command_tool_entries():
            if not valid_llm_tool_name(name) or name in seen:
                continue
            if not self.command_trigger_enabled(name):
                continue
            rows.append(command_tool_schema(name, pattern, "pyylmao_generated_commands"))
            seen.add(name)
        return rows

    def generated_command_tool_entries(self) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        root = self.state.data.setdefault("generated_commands", {})
        for raw_name, entry in sorted(root.items()):
            safe_name = generated_safe_identifier(str(raw_name))
            if not safe_name or not isinstance(entry, dict):
                continue
            path = generated_command_source_path(Path(str(entry.get("path", ""))))
            if path is None:
                continue
            pattern = str(entry.get("pattern") or "")
            if not pattern:
                try:
                    pattern = infer_pattern_from_code(path.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    pattern = ""
            rows.append((safe_name, pattern))
        return rows

    def command_trigger_enabled(self, name: str) -> bool:
        from .triggers import TriggerStore

        return TriggerStore(self.state).enabled(name)

    def execute_command_tool(
        self,
        context: LLMToolContext,
        name: str,
        arguments: dict[str, Any],
    ) -> str | None:
        safe_name = generated_safe_identifier(name)
        if not safe_name or not self.command_tool_exists(safe_name):
            return None
        target = str(arguments.get("channel") or context.target)
        if target != context.target:
            context = LLMToolContext(target=target, history=context.history, state=context.state)
        argv = command_tool_args(arguments)
        generated_output = self.run_generated_command(context, safe_name, argv)
        if generated_output is not None:
            return generated_output
        command_output = self.run_reconstructed_command(context, safe_name, argv)
        if command_output is not None:
            return command_output
        return f"Command tool {safe_name} produced no output"

    def command_tool_exists(self, name: str) -> bool:
        if self.generated_command_entry(name) is not None:
            return True
        return self.command_runner is not None and any(command_name == name for command_name, _, _ in COMMANDS)

    def tool_read_command(self, context: LLMToolContext, name: str = "") -> str:
        del context
        if not str(name).strip():
            return self.command_inventory()
        generated_path = self.generated_command_path(name)
        if generated_path is not None:
            return generated_path.read_text(encoding="utf-8")
        path = self.command_path(name)
        if path is None:
            return f"No command found for {name!r}"
        return path.read_text(encoding="utf-8")

    def tool_write_command(
        self,
        context: LLMToolContext,
        name: str = "",
        content: str = "",
        pattern: str = "",
        code: str = "",
    ) -> str:
        del context
        source = code or content
        if not source:
            return "No command code provided"
        pattern = pattern or infer_pattern_from_code(source)
        safe_name = safe_identifier(name) or infer_command_name_from_pattern(pattern)
        if not safe_name:
            return "Invalid command name"
        self.generated_dir.mkdir(parents=True, exist_ok=True)
        path = self.generated_dir / f"{safe_name}.py"
        path.write_text(source, encoding="utf-8")
        commands = self.state.data.setdefault("generated_commands", {})
        entry = commands.setdefault(safe_name, {})
        entry["path"] = str(path)
        if code and content:
            entry["description"] = content
        if pattern:
            entry["pattern"] = pattern
        entry["updated_at"] = int(time.time())
        self.state.save()
        lines = ["No requirements found in provided code."]
        lines.extend(self.validate_generated_command_load(safe_name, entry))
        return "\n".join(lines)

    def validate_generated_command_load(self, safe_name: str, entry: dict[str, Any]) -> list[str]:
        store = GeneratedCommandStore(self.state)
        lines: list[str] = []
        seen = {safe_name}
        entries = [(safe_name, entry)]
        entries.extend(
            (name, stored_entry)
            for name, stored_entry in store.entries()
            if generated_safe_identifier(name) not in seen
        )
        for name, stored_entry in entries:
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                command = store.load(name, stored_entry)
            if name == safe_name:
                lines.extend(stdout.getvalue().splitlines())
                lines.extend(stderr.getvalue().splitlines())
            if command is None:
                continue
            error_summary = getattr(command.module, "_load_error_summary", "")
            if error_summary:
                lines.append(f"Skipping command {name} due to load error: {error_summary}")
        return lines

    def tool_revise_pattern(self, context: LLMToolContext, name: str, pattern: str) -> str:
        del context
        safe_name = safe_identifier(name)
        if not safe_name:
            return "Invalid command name"
        commands = self.state.data.setdefault("generated_commands", {})
        entry = commands.setdefault(safe_name, {})
        entry["pattern"] = pattern
        entry["updated_at"] = int(time.time())
        self.state.save()
        return f"Pattern for {safe_name} set to {pattern}"

    def tool_install_packages(self, context: LLMToolContext, packages: Any) -> str:
        del context
        names = parse_packages(packages)
        if not names:
            return "No packages requested"
        completed = subprocess.run(
            [sys.executable, "-m", "pip", "install", *names],
            check=False,
            capture_output=True,
            text=True,
            timeout=self.package_timeout,
        )
        output = (completed.stdout + completed.stderr).strip()
        first_lines = "\n".join(output.splitlines()[-20:])
        return f"pip exited {completed.returncode}\n{first_lines}".strip()

    def tool_run(
        self,
        context: LLMToolContext,
        command: str = "",
        cmd_name: str = "",
        args: Any = "",
    ) -> str:
        if cmd_name:
            generated_output = self.run_generated_command(context, cmd_name, parse_run_args(args))
            if generated_output is not None:
                return generated_output
            argv = parse_run_args(args)
            command_output = self.run_reconstructed_command(context, cmd_name, argv)
            if command_output is not None:
                return command_output
            if cmd_name == "exec":
                if not argv:
                    return "No code provided"
                artifact_argv = self.python_artifact_argv(argv)
                if artifact_argv is not None:
                    return self.run_subprocess(artifact_argv, cwd=self.artifact_dir)
                return self.run_subprocess([sys.executable, "-c", argv[0]])
            if cmd_name in {"python", "python3"}:
                artifact_argv = self.python_artifact_argv(argv)
                if artifact_argv is not None:
                    return self.run_subprocess(artifact_argv, cwd=self.artifact_dir)
                return self.run_subprocess([sys.executable, *argv])
            return self.run_subprocess([cmd_name, *argv])
        if not command:
            return "No command provided"
        completed = subprocess.run(
            command,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            timeout=self.run_timeout,
        )
        output = (completed.stdout + completed.stderr).strip()
        if len(output) > 4000:
            output = output[:4000] + "\n... truncated ..."
        return f"exit={completed.returncode}\n{output}".strip()

    def run_subprocess(self, argv: list[str], cwd: Path | None = None) -> str:
        try:
            completed = subprocess.run(
                argv,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.run_timeout,
                cwd=cwd,
            )
        except OSError as exc:
            return f"run failed: {exc}"
        output = (completed.stdout + completed.stderr).strip()
        if len(output) > 4000:
            output = output[:4000] + "\n... truncated ..."
        return f"exit={completed.returncode}\n{output}".strip()

    def python_artifact_argv(self, argv: list[str]) -> list[str] | None:
        if not argv:
            return None
        path = self.resolve_artifact_script(argv[0])
        if path is None:
            return None
        return [sys.executable, str(path), *argv[1:]]

    def resolve_artifact_script(self, name: str) -> Path | None:
        raw = str(name).strip().replace("\\", "/")
        if not raw:
            return None
        candidates = [raw]
        if "/" not in raw and not raw.endswith(".py"):
            candidates.append(f"{raw}.py")
        if raw.startswith("/"):
            candidates.append(raw.rsplit("/", 1)[-1])
            if not raw.endswith(".py"):
                candidates.append(f"{raw.rsplit('/', 1)[-1]}.py")
        for candidate in candidates:
            artifact = safe_artifact_path(self.artifact_dir, candidate)
            if artifact is None:
                continue
            path, _ = artifact
            if path.exists() and path.is_file():
                return path
        return None

    def run_generated_command(
        self,
        context: LLMToolContext,
        cmd_name: str,
        args: list[str],
    ) -> str | None:
        safe_name = generated_safe_identifier(cmd_name)
        if not safe_name:
            return None
        entry = self.generated_command_entry(safe_name)
        if entry is None:
            return None
        store = GeneratedCommandStore(self.state)
        command = store.load(safe_name, entry)
        if command is None:
            return None
        lines = store.run_with_args(command, args, BOT_NICK, context.target)
        return "\n".join(lines) if lines else "None"

    def run_reconstructed_command(
        self,
        context: LLMToolContext,
        cmd_name: str,
        args: list[str],
    ) -> str | None:
        if self.command_runner is None:
            return None
        result = self.command_runner(context, cmd_name, args)
        if result is None:
            return None
        if isinstance(result, list):
            return "\n".join(str(line) for line in result) if result else "None"
        return str(result)

    def tool_get_chat_history(
        self,
        context: LLMToolContext,
        channel: str = "",
        max_lines: Any = "100",
        include_bot: Any = "False",
    ) -> str:
        try:
            limit = max(0, min(int(max_lines), 20000))
        except (TypeError, ValueError):
            limit = 100
        if limit == 0:
            return ToolResult("No chat history available.", trace_label="after filter")
        requested_channel = str(channel or context.target)
        include_bot_messages = parse_bool(include_bot)

        if context.state is not None:
            lines = []
            for item in history_items(context.state, requested_channel):
                if item.get("role") == "assistant" and not include_bot_messages:
                    continue
                nick = str(item.get("nickname") or BOT_NICK)
                message = str(item.get("message") or "")
                lines.append(f"{nick}: {message}")
            lines = lines[-limit:]
            if lines:
                return ToolResult("\n".join(lines), trace_label="from chat history")

        lines = [f"{nick}: {message}" for nick, message in context.history[-limit:]]
        result = "\n".join(lines) if lines else "No chat history available."
        return ToolResult(result, trace_label="after filter")

    def tool_irc_command(self, context: LLMToolContext, command: str) -> str:
        raw_command = str(command).strip()
        if not raw_command:
            return "No IRC command provided"
        commands = split_irc_commands(raw_command)
        history = self.state.data.setdefault("irc_command_log", [])
        for item in commands:
            history.append({"ts": int(time.time()), "target": context.target, "command": item})
        if len(history) > 1000:
            del history[:-1000]
        self.state.save()
        if self.raw_irc_sender is not None:
            return str(self.raw_irc_sender(commands))
        return "\n".join(f"queued IRC command: {item}" for item in commands)

    def tool_channel_list(self, context: LLMToolContext) -> str:
        del context
        channels = self.known_channels()
        return "\n".join(channels) if channels else "No channels known."

    def tool_get_channel_users(self, context: LLMToolContext, channel: str = "") -> str:
        requested_channel = str(channel or context.target)
        found, users = nested_kv_get(
            self.state.data,
            ["kvstore", "pyylmao", "irc", "channels", requested_channel, "users"],
        )
        if not found or not users:
            return f"No users known for {requested_channel}."
        if isinstance(users, dict):
            return "\n".join(str(name) for name in users)
        if isinstance(users, list):
            return "\n".join(str(item) for item in users)
        return str(users)

    def tool_llm_version(self, context: LLMToolContext) -> str:
        del context
        return "pyylmao llm tools v0.0.0"

    def tool_llm_time(self, context: LLMToolContext) -> str:
        del context
        return datetime.now(timezone.utc).isoformat()

    def tool_eval(self, context: LLMToolContext, code: str = "") -> str:
        del context
        if not str(code).strip():
            return "No code provided"
        return self.run_subprocess([sys.executable, "-c", str(code)])

    def tool_read_skill(self, context: LLMToolContext, name: str) -> str:
        del context
        skills = self.state.data.setdefault("skills", {})
        requested = str(name).strip()
        if requested in skills:
            return str(skills[requested])
        folded = requested.casefold()
        for skill_name, content in skills.items():
            if str(skill_name).casefold() == folded:
                return str(content)
        builtin_name = builtin_skill_name(requested)
        if builtin_name is not None:
            return BUILTIN_SKILLS[builtin_name]
        return f"No skill named {name}"

    def tool_list_skills(self, context: LLMToolContext) -> str:
        del context
        skills = self.merged_skills()
        return "\n".join(sorted(skills)) or "No skills."

    def tool_create_skill(self, context: LLMToolContext, name: str, content: str) -> str:
        del context
        safe_name = name.strip()
        if not safe_name:
            return "Invalid skill name"
        skills = self.state.data.setdefault("skills", {})
        skills[safe_name] = content
        self.state.save()
        return f"Done! Created the {safe_name} skill."

    def tool_query_skills(self, context: LLMToolContext, query: str) -> str:
        del context
        needle = str(query).strip().casefold()
        if not needle:
            return self.tool_list_skills(context)
        skills = self.merged_skills()
        matches = []
        for name, content in sorted(skills.items()):
            text = str(content)
            if needle in name.casefold() or needle in text.casefold():
                lines = text.splitlines()
                excerpt = first_matching_line(text, needle) or (lines[0] if lines else "")
                matches.append(f"{name}: {excerpt[:240]}")
        return "\n".join(matches[:20]) or "No matching skills."

    def tool_update_skill(self, context: LLMToolContext, name: str, content: str) -> str:
        del context
        safe_name = name.strip()
        if not safe_name:
            return "Invalid skill name"
        skills = self.state.data.setdefault("skills", {})
        if safe_name not in skills:
            return f"No skill named {safe_name}"
        skills[safe_name] = content
        self.state.save()
        return f"Done! Updated the {safe_name} skill."

    def merged_skills(self) -> dict[str, str]:
        skills = {
            str(name): str(content)
            for name, content in self.state.data.setdefault("skills", {}).items()
        }
        hidden_builtins = {
            builtin_name
            for name in skills
            for builtin_name in [builtin_skill_name(name)]
            if builtin_name is not None
        }
        merged = {
            name: content
            for name, content in BUILTIN_SKILLS.items()
            if name not in hidden_builtins
        }
        merged.update(skills)
        return merged

    def tool_remember(self, context: LLMToolContext, text: str = "", memories: Any = None) -> str:
        del context
        entries = parse_memory_entries(memories) if memories is not None else []
        if text:
            entries.append({"text": str(text)})
        if not entries:
            return "No memory provided"
        stored = self.state.data.setdefault("memories", [])
        ts = int(time.time())
        first_id = len(stored) + 1
        for entry in entries:
            memory_id = len(stored) + 1
            item = {"id": memory_id, "text": memory_text(entry), "ts": ts}
            if isinstance(entry, dict):
                if "key" in entry:
                    item["key"] = str(entry.get("key", ""))
                if "value" in entry:
                    item["value"] = str(entry.get("value", ""))
            stored.append(item)
        self.state.save()
        if len(entries) == 1:
            return f"Remembered #{first_id}"
        return f"Remembered {len(entries)} memories"

    def tool_forget(self, context: LLMToolContext, query: str = "", keys: Any = None) -> str:
        del context
        memories = self.state.data.setdefault("memories", [])
        terms = parse_query_list(keys) if keys is not None else []
        if query:
            terms.extend(parse_query_list(query))
        if not terms:
            return "No memory key or query provided"
        before = len(memories)
        memories[:] = [
            item for item in memories
            if not any(memory_matches(item, term) for term in terms)
        ]
        self.state.save()
        return f"Forgot {before - len(memories)} memories"

    def tool_search_memories(self, context: LLMToolContext, queries: Any) -> str:
        del context
        needles = parse_query_list(queries)
        memories = self.state.data.setdefault("memories", [])
        matches = []
        for item in memories:
            text = memory_display(item)
            haystack = memory_haystack(item)
            if any(memory_search_matches(haystack, needle) for needle in needles):
                matches.append(f"#{item.get('id')}: {text}")
        return "\n".join(matches[:20]) or "No memories found."

    def tool_semantic_search(
        self,
        context: LLMToolContext,
        query: str = "",
        phrases: Any = "",
        profile: str = "",
    ) -> str:
        del context
        profile_name = normalize_search_profile(profile)
        search_query = semantic_search_query(query, phrases)
        if not search_query:
            return f"Profile: {profile_name}\nNo search query provided."
        try:
            results = self.web_searcher(search_query, profile_name)
        except (OSError, TimeoutError, HTTPError, URLError) as exc:
            return f"Profile: {profile_name}\nSearch error: {exc}"
        return format_web_search_results(profile_name, search_query, results)

    def tool_read_artifact(self, context: LLMToolContext, filename: str) -> str:
        del context
        artifact = safe_artifact_path(self.artifact_dir, filename)
        if artifact is None:
            return "Invalid artifact filename"
        path, relative_name = artifact
        if not path.exists() or not path.is_file():
            generated_path = self.generated_artifact_command_path(relative_name)
            if generated_path is not None:
                return generated_path.read_text(encoding="utf-8", errors="replace")[:12000]
            if relative_name.startswith("attachment_"):
                return "Unable to access attachment. Please verifythe file or provide additional details."
            return f"Error: {relative_name.rsplit('/', 1)[-1]}"
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[:12000]

    def tool_save_artifact(
        self,
        context: LLMToolContext,
        filename: str = "",
        contents: str = "",
        content: str = "",
        create_dirs: Any = "",
    ) -> str:
        del context, create_dirs
        artifact = safe_artifact_path(
            self.artifact_dir,
            filename or f"artifact_{int(time.time())}.txt",
        )
        if artifact is None:
            return "Invalid artifact filename"
        path, relative_name = artifact
        payload = contents if contents else content
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(payload), encoding="utf-8")
        return f"━━☛ New artifact: {artifact_url(relative_name)}"

    def tool_list_artifacts(self, context: LLMToolContext, subdir: str = "") -> str:
        del context
        artifact_dir = safe_artifact_dir(self.artifact_dir, subdir)
        if artifact_dir is None:
            return "Invalid artifact directory"
        path, relative_name = artifact_dir
        if not path.exists():
            return f"No artifact directory named {relative_name}" if relative_name else "No artifacts found."
        if not path.is_dir():
            return f"{relative_name} is not a directory"
        entries = []
        for child in sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.casefold())):
            name = child.name + ("/" if child.is_dir() else "")
            entries.append(f"{relative_name}/{name}" if relative_name else name)
        return "\n".join(entries[:200]) or "No artifacts found."

    def command_path(self, name: str) -> Path | None:
        raw_name = str(name).strip().lower()
        raw_module = RAW_COMMAND_MODULES.get(raw_name)
        if raw_module:
            path = self.source_root / f"{raw_module}.py"
            return path if path.exists() and path.is_file() else None
        safe_name = safe_identifier(name)
        if not safe_name:
            return None
        module = COMMAND_MODULES.get(safe_name, safe_name)
        candidates = [self.source_root / f"{module}.py"]
        for command_name, _, _ in COMMANDS:
            if command_name == safe_name:
                candidates.append(self.source_root / f"{COMMAND_MODULES.get(command_name, command_name)}.py")
        for path in candidates:
            if path.exists() and path.is_file():
                return path
        return None

    def generated_command_path(self, name: str) -> Path | None:
        safe_name = safe_identifier(name)
        if not safe_name:
            return None
        entry = self.generated_command_entry(safe_name)
        if entry is None:
            return None
        return generated_command_source_path(Path(str(entry.get("path", ""))))

    def generated_artifact_command_path(self, relative_name: str) -> Path | None:
        parts = [part for part in str(relative_name).replace("\\", "/").split("/") if part]
        if not parts:
            return None
        command_name = ""
        if len(parts) >= 2 and parts[-1] == "__init__.py":
            command_name = parts[-2]
        elif len(parts) >= 2 and parts[-2] == "commands" and parts[-1].endswith(".py"):
            command_name = parts[-1][:-3]
        if not command_name:
            return None
        return self.generated_command_path(command_name)

    def generated_command_entry(self, safe_name: str) -> dict[str, Any] | None:
        entry = self.state.data.setdefault("generated_commands", {}).get(safe_name)
        if isinstance(entry, dict):
            path = generated_command_source_path(Path(str(entry.get("path", ""))))
            if path is not None:
                return entry
        path = generated_command_source_path(self.generated_dir / f"{safe_name}.py")
        if path is None:
            path = generated_command_source_path(self.generated_dir / safe_name)
        if path is None:
            return None
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            source = ""
        return {"path": str(path), "pattern": infer_pattern_from_code(source)}

    def command_inventory(self) -> str:
        lines = ["Generated commands:"]
        generated = self.state.data.setdefault("generated_commands", {})
        for name in sorted(generated):
            entry = generated[name]
            if not isinstance(entry, dict):
                continue
            pattern = entry.get("pattern", "")
            lines.append(f"- {name}: {pattern}")
        if len(lines) == 1:
            lines.append("- none")
        lines.append("Built-in commands:")
        for name, _, pattern in COMMANDS:
            lines.append(f"- {name}: {pattern}")
        return "\n".join(lines)

    def known_channels(self) -> list[str]:
        found, channels = nested_kv_get(self.state.data, ["kvstore", "pyylmao", "irc", "channels"])
        if isinstance(channels, dict):
            return sorted(str(name) for name in channels)
        if found and isinstance(channels, list):
            return sorted(str(name) for name in channels)
        return []


class BoundLLMTools:
    def __init__(self, registry: LLMToolRegistry, context: LLMToolContext):
        self.registry = registry
        self.context = context

    def schemas(self) -> list[dict[str, Any]]:
        return self.registry.schemas()

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        return self.registry.execute(self.context, name, arguments)


def schema(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def command_tool_schema(name: str, pattern: str, plugin: str) -> dict[str, Any]:
    return schema(
        name,
        (
            f"Run pyylmao command {name!r} as an LLM tool. Pass only the text "
            f"after the IRC trigger in args. Trigger pattern: {pattern}."
        ),
        {
            "args": {
                "type": "string",
                "description": "Command arguments as text, or a JSON/Python list literal.",
            },
            "channel": {
                "type": "string",
                "description": "Optional target channel override.",
            },
        },
        [],
    )


def valid_llm_tool_name(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", str(name)))


def command_tool_args(arguments: dict[str, Any]) -> list[str]:
    if "args" in arguments:
        return parse_run_args(arguments["args"])
    if "text" in arguments:
        return parse_run_args(arguments["text"])
    if "query" in arguments:
        return parse_run_args(arguments["query"])
    if not arguments:
        return []
    return [str(value) for key, value in arguments.items() if key != "channel"]


def safe_identifier(name: str) -> str:
    raw = str(name).strip().lower().replace("\\", "/").rsplit("/", 1)[-1]
    if raw.endswith(".py"):
        raw = raw[:-3]
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", raw).strip("_")
    return safe


def parse_packages(packages: Any) -> list[str]:
    if isinstance(packages, str):
        try:
            parsed = ast.literal_eval(packages)
        except (SyntaxError, ValueError):
            parsed = packages.split()
    else:
        parsed = packages
    if isinstance(parsed, str):
        parsed = [parsed]
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if str(item).strip()]


def parse_run_args(args: Any) -> list[str]:
    if args in (None, ""):
        return []
    if isinstance(args, list):
        return [str(item) for item in args]
    if not isinstance(args, str):
        return [str(args)]
    try:
        parsed = json.loads(args)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(args)
        except (SyntaxError, ValueError):
            return [args]
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    return [str(parsed)]


def parse_query_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if not isinstance(value, str):
        return [str(value)]
    try:
        parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        parsed = None
    if isinstance(parsed, list):
        return [str(item) for item in parsed if str(item).strip()]
    return [item for item in re.split(r"[, ]+", value) if item]


def parse_memory_entries(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    parsed = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(value)
            except (SyntaxError, ValueError):
                parsed = value
    if isinstance(parsed, list):
        return [item for item in parsed if item not in (None, "")]
    return [parsed]


def memory_text(entry: Any) -> str:
    if isinstance(entry, dict):
        key = str(entry.get("key", "")).strip()
        value = entry.get("value")
        text = str(entry.get("text") or entry.get("memory") or entry.get("content") or "").strip()
        if key and value not in (None, ""):
            return f"{key}: {value}"
        if text:
            return text
        if value not in (None, ""):
            return str(value)
    return str(entry)


def memory_display(item: Any) -> str:
    if not isinstance(item, dict):
        return str(item)
    key = str(item.get("key", "")).strip()
    value = item.get("value")
    if key and value not in (None, ""):
        return f"{key}: {value}"
    return str(item.get("text", ""))


def memory_haystack(item: Any) -> str:
    if not isinstance(item, dict):
        return str(item).casefold()
    return "\n".join(
        str(item.get(name, ""))
        for name in ("id", "key", "value", "text")
    ).casefold()


def memory_matches(item: Any, term: str) -> bool:
    query = str(term).strip()
    if not query:
        return False
    if isinstance(item, dict) and query.isdigit() and item.get("id") == int(query):
        return True
    needle = query.casefold()
    return needle in memory_haystack(item)


def memory_search_matches(haystack: str, term: str) -> bool:
    needle = str(term).strip()
    if not needle:
        return False
    try:
        if re.search(needle, haystack, re.IGNORECASE):
            return True
    except re.error:
        pass
    return needle.casefold() in haystack


def normalize_search_profile(profile: str) -> str:
    name = str(profile).strip().casefold()
    if name in {"instant", "balanced", "news", "comprehensive", "web_search"}:
        return name
    return "balanced"


def semantic_search_query(query: str = "", phrases: Any = "") -> str:
    parts = [str(query).strip(), *parse_query_list(phrases)]
    seen: set[str] = set()
    deduped: list[str] = []
    for part in parts:
        cleaned = " ".join(str(part).split())
        if not cleaned:
            continue
        folded = cleaned.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        deduped.append(cleaned)
    return " ".join(deduped)


def default_web_search(query: str, profile: str) -> list[WebSearchResult]:
    limit = search_result_limit(profile)
    url = f"https://html.duckduckgo.com/html/?q={quote(query, safe='')}"
    request = Request(
        url,
        headers={
            "User-Agent": "pyylmao/0.1 (+https://cte.pcp.ovh/2/commands.html)",
        },
    )
    with urlopen(request, timeout=12) as response:
        page = response.read().decode("utf-8", errors="replace")
    return parse_duckduckgo_html(page, limit)


def search_result_limit(profile: str) -> int:
    if profile == "instant":
        return 3
    if profile == "comprehensive":
        return 8
    return 5


def parse_duckduckgo_html(page: str, limit: int = 5) -> list[WebSearchResult]:
    link_re = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>',
        flags=re.IGNORECASE | re.DOTALL,
    )
    matches = list(link_re.finditer(page))
    results: list[WebSearchResult] = []
    for index, match in enumerate(matches):
        title = clean_html(match.group("title"))
        url = normalize_search_result_url(match.group("href"))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else start + 2500
        snippet = search_result_snippet(page[start:end])
        if not title or not url:
            continue
        results.append(WebSearchResult(title=title, url=url, snippet=snippet))
        if len(results) >= limit:
            break
    return results


def normalize_search_result_url(raw_url: str) -> str:
    url = unescape(str(raw_url).strip())
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlparse(url)
    if parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg")
        if target:
            return unquote(target[0])
    return url


def search_result_snippet(segment: str) -> str:
    snippet_match = re.search(
        r'class="result__snippet"[^>]*>(?P<snippet>.*?)</(?:a|div)>',
        segment,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not snippet_match:
        return ""
    return clean_html(snippet_match.group("snippet"))


def clean_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    return " ".join(unescape(text).split())


def format_web_search_results(
    profile: str,
    query: str,
    results: list[WebSearchResult],
) -> str:
    lines = [f"Profile: {profile}", f"Query: {query}"]
    if not results:
        lines.append("No web results found.")
        return "\n".join(lines)
    for index, result in enumerate(results[: search_result_limit(profile)], start=1):
        lines.append(f"{index}. {result.title}")
        lines.append(f"   URL: {result.url}")
        if result.snippet:
            lines.append(f"   {result.snippet}")
    return "\n".join(lines)


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().casefold() in {"1", "true", "t", "yes", "y", "on"}


def first_matching_line(text: str, needle: str) -> str:
    lowered = needle.casefold()
    for line in text.splitlines():
        if lowered in line.casefold():
            return line.strip()
    return ""


def split_irc_commands(command: str) -> list[str]:
    return [line.strip() for line in command.replace("\r", "\n").split("\n") if line.strip()]


def default_artifact_dir(state: JsonState) -> Path:
    configured = os.getenv("PYYLMAO_ARTIFACT_DIR") or os.getenv("PYYLMAO_WWW_DIR")
    return Path(configured) if configured else state.path.parent / "artifacts"


def safe_artifact_path(root: Path, filename: str) -> tuple[Path, str] | None:
    raw = str(filename).strip().replace("\\", "/").lstrip("/")
    parts = [part for part in raw.split("/") if part and part != "."]
    if not parts or any(part == ".." for part in parts):
        return None
    relative_name = "/".join(parts)
    root_resolved = root.resolve()
    path = (root / relative_name).resolve()
    try:
        path.relative_to(root_resolved)
    except ValueError:
        return None
    return path, relative_name


def safe_artifact_dir(root: Path, subdir: str) -> tuple[Path, str] | None:
    raw = str(subdir).strip().replace("\\", "/").lstrip("/")
    parts = [part for part in raw.split("/") if part and part != "."]
    if any(part == ".." for part in parts):
        return None
    relative_name = "/".join(parts)
    root_resolved = root.resolve()
    path = (root / relative_name).resolve()
    try:
        path.relative_to(root_resolved)
    except ValueError:
        return None
    return path, relative_name


def artifact_url(relative_name: str) -> str:
    quoted = "/".join(quote(part) for part in relative_name.split("/"))
    return f"{_base_url(None).rstrip('/')}/{quoted}"


def nested_kv_get(root: Any, path: list[str]) -> tuple[bool, Any]:
    current = root
    for part in path:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return False, None
    return True, current


def parse_tool_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(str(raw))
        except (SyntaxError, ValueError):
            return {}
    return parsed if isinstance(parsed, dict) else {}


def infer_pattern_from_code(code: str) -> str:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        tree = None
    if tree is not None:
        for node in tree.body:
            if isinstance(node, ast.Assign):
                if not any(isinstance(target, ast.Name) and target.id == "pattern" for target in node.targets):
                    continue
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    return node.value.value
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if not isinstance(item, ast.Assign):
                        continue
                    if not any(isinstance(target, ast.Name) and target.id == "pattern" for target in item.targets):
                        continue
                    if isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                        return item.value.value
    match = re.search(
        r"(?m)^\s*pattern\s*=\s*r?(?P<quote>['\"])(?P<value>.*?)(?P=quote)\s*$",
        code,
    )
    return match.group("value") if match else ""


def infer_command_name_from_pattern(pattern: str) -> str:
    text = str(pattern).strip()
    candidates = [
        r"^\^?\\?[!?\.](?:\(\?P?<[^>]+>)?(?P<name>[A-Za-z0-9][A-Za-z0-9_-]*)",
        r"^\^?\\?[!?\.]\(\?:(?P<name>[A-Za-z0-9][A-Za-z0-9_-]*)",
        r"^\^?\(\[\!\?\]\)(?P<name>[A-Za-z0-9][A-Za-z0-9_-]*)",
        r"^\^?\[[^\]]*[!?\.][^\]]*\](?P<name>[A-Za-z0-9][A-Za-z0-9_-]*)",
    ]
    for candidate in candidates:
        match = re.search(candidate, text)
        if match:
            return safe_identifier(match.group("name"))
    return ""


def format_tool_args(arguments: dict[str, Any]) -> str:
    display = {
        key: shorten(value)
        for key, value in arguments.items()
    }
    return repr(display)


def shorten(value: Any, limit: int = 120) -> Any:
    if not isinstance(value, str):
        return value
    collapsed = value.replace("\n", " | ")
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 18] + f" ... (+{len(collapsed) - limit + 18} chars)"
