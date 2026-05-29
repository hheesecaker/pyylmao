from __future__ import annotations

import contextlib
import asyncio
import ast
import importlib.util
import inspect
import io
import os
import re
import sys
import threading
import traceback
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from .formatting import clean_nick
from . import ircbot
from .history_store import normalize_channel_user
from .kv.backends.sqlite import KvContext, configure_default_state
from .state import JsonState


@dataclass
class LoadedCommand:
    name: str
    path: Path
    pattern: str
    module: ModuleType
    mtime: float


@dataclass(frozen=True)
class EventSource:
    nick: str
    user: str = ""
    host: str = ""

    @property
    def nickname(self) -> str:
        return self.nick

    @property
    def username(self) -> str:
        return self.user

    @property
    def hostname(self) -> str:
        return self.host

    def __str__(self) -> str:
        if self.user or self.host:
            return f"{self.nick}!{self.user}@{self.host}"
        return self.nick


@dataclass(frozen=True)
class MessageEvent:
    event_type: str
    text: str
    raw_line: str
    channel: str
    nickname: str
    username: str = ""
    hostname: str = ""
    target: str = ""
    channels: tuple[str, ...] = ()

    @property
    def arguments(self) -> tuple[str, ...]:
        return (self.text,) if self.text else ()

    @property
    def args(self) -> tuple[str, ...]:
        return self.arguments

    @property
    def source(self) -> EventSource:
        return EventSource(self.nickname, self.username, self.hostname)

    @property
    def type(self) -> str:
        return self.event_type


@dataclass(frozen=True)
class GeneratedCommandReply:
    target: str
    lines: list[str]


class Attachment:
    def __init__(
        self,
        type: str | None = None,
        path: str | None = None,
        url: str | None = None,
        content: bytes | str | None = None,
    ) -> None:
        self.type = type
        self.path = path
        self.url = url
        self.content = content

    def content_bytes(self) -> bytes | None:
        if self.content is not None:
            if isinstance(self.content, bytes):
                return self.content
            return str(self.content).encode("utf-8")
        if self.path:
            with open(self.path, "rb") as handle:
                return handle.read()
        return None


@dataclass(frozen=True)
class GeneratedTool:
    name: str
    plugin: str
    enabled: bool
    kind: str = "llm_tool"
    pattern: str = ""
    state: JsonState | None = None
    event: "MessageEvent | None" = None
    raw_irc_sender: Callable[[list[str]], str] | None = None

    def __getitem__(self, key: str) -> Any:
        if key == "name":
            return self.name
        if key == "plugin":
            return self.plugin
        if key == "enabled":
            return self.enabled
        raise KeyError(key)

    def __call__(self, *args: Any, **kwargs: Any) -> str:
        return self.execute(*args, **kwargs)

    def run(self, *args: Any, **kwargs: Any) -> str:
        return self.execute(*args, **kwargs)

    def execute(self, *args: Any, **kwargs: Any) -> str:
        if self.state is None:
            raise RuntimeError(f"Tool {self.name} is not bound to bot state")
        from .llm_tools import LLMToolContext, LLMToolRegistry

        event = self.event or MessageEvent(
            event_type="privmsg",
            text="",
            raw_line="",
            channel="",
            nickname=os.getenv("PYYLMAO_NICK") or "pyylmao",
            target="",
        )
        arguments = generated_tool_arguments(args, kwargs)
        target = str(arguments.get("channel") or event.channel or event.target or "")
        if self.kind == "generated_command":
            return self.execute_generated_command(arguments, event, target)
        context = LLMToolContext(target=target, history=(), state=self.state)
        registry = LLMToolRegistry(self.state, raw_irc_sender=self.raw_irc_sender)
        return registry.execute(context, self.name, arguments)

    def execute_generated_command(
        self,
        arguments: dict[str, Any],
        event: "MessageEvent",
        target: str,
    ) -> str:
        from .llm_tools import command_tool_args

        assert self.state is not None
        entry = self.state.data.setdefault("generated_commands", {}).get(self.name)
        if not isinstance(entry, dict):
            raise RuntimeError(f"No generated command named {self.name}")
        store = GeneratedCommandStore(self.state, raw_irc_sender=self.raw_irc_sender)
        command = store.load(self.name, entry)
        if command is None:
            raise RuntimeError(f"No generated command named {self.name}")
        lines = store.run_with_args(
            command,
            command_tool_args(arguments),
            event.nickname or os.getenv("PYYLMAO_NICK") or "pyylmao",
            target,
            event,
        )
        return "\n".join(lines) if lines else "None"

    def __iter__(self):
        return iter(self.to_dict().items())

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "plugin": self.plugin, "enabled": self.enabled}


class GeneratedToolRegistry:
    def __init__(self, tools: list[GeneratedTool]) -> None:
        self._tools = tools
        self._by_name = {tool.name: tool for tool in tools}
        self._by_name.update({f"default_api:{tool.name}": tool for tool in tools})

    def __iter__(self):
        return iter(self._tools)

    def __len__(self) -> int:
        return len(self._tools)

    def __bool__(self) -> bool:
        return bool(self._tools)

    def __contains__(self, name: object) -> bool:
        return str(name) in self._by_name

    def __getitem__(self, key: int | slice | str) -> Any:
        if isinstance(key, (int, slice)):
            return self._tools[key]
        return self._by_name[key]

    def get(self, name: str, default: Any = None) -> GeneratedTool | Any:
        return self._by_name.get(str(name), default)

    def keys(self):
        return self._by_name.keys()

    def values(self):
        return list(self._tools)

    def items(self):
        return ((tool.name, tool) for tool in self._tools)

    def names(self) -> list[str]:
        return [tool.name for tool in self._tools]

    def to_dict(self) -> dict[str, dict[str, Any]]:
        return {tool.name: tool.to_dict() for tool in self._tools}


class Toolbox:
    pattern = ""
    trigger_on: str | list[str] = "pubmsg"
    match_field = "text"
    send_to: str | list[str] | None = None

    def _onload(self) -> None:
        return None


class Channel(dict):
    def __init__(self, name: str = "", users: Any = None) -> None:
        super().__init__()
        self.name = name
        self.userdict = self
        for nickname, metadata in normalize_channel_users(users):
            self[nickname] = metadata

    def users(self) -> list[str]:
        return list(self.keys())

    def has_user(self, nickname: str) -> bool:
        return channel_user_key(self, nickname) is not None

    def add_user(self, nickname: str) -> None:
        clean = normalize_channel_user(nickname)
        if clean:
            self.setdefault(clean, {})

    def remove_user(self, nickname: str) -> None:
        key = channel_user_key(self, nickname)
        if key is not None:
            del self[key]

    def change_nick(self, before: str, after: str) -> None:
        key = channel_user_key(self, before)
        clean_after = normalize_channel_user(after)
        if key is None or not clean_after:
            return
        self[clean_after] = self.pop(key)

    def opers(self) -> list[str]:
        return self._mode_users("o", "@")

    def voiced(self) -> list[str]:
        return self._mode_users("v", "+")

    def halfops(self) -> list[str]:
        return self._mode_users("h", "%")

    def owners(self) -> list[str]:
        return self._mode_users("q", "~")

    def admins(self) -> list[str]:
        return self._mode_users("a", "&")

    def is_oper(self, nickname: str) -> bool:
        return self._has_mode(nickname, "o", "@")

    def is_voiced(self, nickname: str) -> bool:
        return self._has_mode(nickname, "v", "+")

    def is_halfop(self, nickname: str) -> bool:
        return self._has_mode(nickname, "h", "%")

    def is_owner(self, nickname: str) -> bool:
        return self._has_mode(nickname, "q", "~")

    def is_admin(self, nickname: str) -> bool:
        return self._has_mode(nickname, "a", "&")

    def _mode_users(self, mode: str, prefix: str) -> list[str]:
        return [nickname for nickname in self if self._has_mode(nickname, mode, prefix)]

    def _has_mode(self, nickname: str, mode: str, prefix: str) -> bool:
        key = channel_user_key(self, nickname)
        if key is None:
            return False
        metadata = self.get(key)
        if isinstance(metadata, dict):
            modes = str(metadata.get("modes") or metadata.get("mode") or "")
            prefixes = str(metadata.get("prefixes") or metadata.get("prefix") or "")
            return mode in modes or prefix in prefixes
        return False


class ChannelMap(dict):
    def __missing__(self, key: str) -> Channel:
        channel = Channel(str(key))
        self[str(key)] = channel
        return channel


class ConnectionProxy:
    def __init__(
        self,
        nickname: str | None = None,
        state: JsonState | None = None,
        event: MessageEvent | None = None,
    ) -> None:
        self.commands: list[str] = []
        self._nickname = nickname or os.getenv("PYYLMAO_NICK") or "pyylmao"
        self.reactor = ReactorProxy(self)
        self.channels = channel_map_from_state(state, event)

    def get_nickname(self) -> str:
        return self._nickname

    def get_server_name(self) -> str:
        return ""

    def is_connected(self) -> bool:
        return True

    def privmsg(self, target: str, text: str) -> None:
        self.commands.append(f"PRIVMSG {target} :{text}")

    def privmsg_many(self, targets, text: str) -> None:
        for target in normalize_targets(targets):
            self.privmsg(target, text)

    def notice(self, target: str, text: str) -> None:
        self.commands.append(f"NOTICE {target} :{text}")

    def action(self, target: str, text: str) -> None:
        self.commands.append(f"PRIVMSG {target} :\x01ACTION {text}\x01")

    def ctcp(self, target: str, tag: str, data: str = "") -> None:
        payload = str(tag).upper() + (f" {data}" if data else "")
        self.commands.append(f"PRIVMSG {target} :\x01{payload}\x01")

    def ctcp_reply(self, target: str, tag: str, data: str = "") -> None:
        payload = str(tag).upper() + (f" {data}" if data else "")
        self.commands.append(f"NOTICE {target} :\x01{payload}\x01")

    def join(self, channel: str) -> None:
        self.commands.append(f"JOIN {channel}")

    def part(self, channel: str, message: str = "") -> None:
        command = f"PART {channel}" + (f" :{message}" if message else "")
        self.commands.append(command)

    def whois(self, nickname: str) -> None:
        self.commands.append(f"WHOIS {nickname}")

    def names(self, channels: str = "") -> None:
        self.commands.append("NAMES" + (f" {channels}" if channels else ""))

    def list(self, channels: str = "") -> None:
        self.commands.append("LIST" + (f" {channels}" if channels else ""))

    def topic(self, channel: str, new_topic: str | None = None) -> None:
        self.commands.append(f"TOPIC {channel}" + (f" :{new_topic}" if new_topic is not None else ""))

    def admin(self, server: str = "") -> None:
        self.commands.append("ADMIN" + (f" {server}" if server else ""))

    def info(self, server: str = "") -> None:
        self.commands.append("INFO" + (f" {server}" if server else ""))

    def ison(self, *nicknames: str) -> None:
        self.commands.append("ISON " + " ".join(str(nick) for nick in nicknames))

    def links(self, remote_server: str = "", server_mask: str = "") -> None:
        suffix = " ".join(item for item in [remote_server, server_mask] if item)
        self.commands.append("LINKS" + (f" {suffix}" if suffix else ""))

    def lusers(self, server: str = "") -> None:
        self.commands.append("LUSERS" + (f" {server}" if server else ""))

    def motd(self, server: str = "") -> None:
        self.commands.append("MOTD" + (f" {server}" if server else ""))

    def oper(self, name: str, password: str) -> None:
        self.commands.append(f"OPER {name} {password}")

    def pass_(self, password: str) -> None:
        self.commands.append(f"PASS {password}")

    def ping(self, target: str, target2: str = "") -> None:
        self.commands.append(f"PING {target}" + (f" {target2}" if target2 else ""))

    def pong(self, target: str, target2: str = "") -> None:
        self.commands.append(f"PONG {target}" + (f" {target2}" if target2 else ""))

    def invite(self, nickname: str, channel: str) -> None:
        self.commands.append(f"INVITE {nickname} :{channel}")

    def kick(self, channel: str, nickname: str, comment: str = "") -> None:
        command = f"KICK {channel} {nickname}" + (f" :{comment}" if comment else "")
        self.commands.append(command)

    def mode(self, target: str, *args: str) -> None:
        suffix = " ".join(str(item) for item in args if str(item))
        self.commands.append(f"MODE {target}" + (f" {suffix}" if suffix else ""))

    def nick(self, nickname: str) -> None:
        self.commands.append(f"NICK {nickname}")

    def quit(self, message: str = "") -> None:
        self.commands.append("QUIT" + (f" :{message}" if message else ""))

    def disconnect(self, message: str = "") -> None:
        self.quit(message)

    def send_raw(self, command: str) -> None:
        self.commands.append(str(command))

    def send_raw_OLD(self, command: str) -> None:
        self.send_raw(command)

    def send_items(self, command: str, *items: str) -> None:
        suffix = " ".join(str(item) for item in items if str(item))
        self.commands.append(str(command).upper() + (f" {suffix}" if suffix else ""))

    def cap(self, subcommand: str, *args: str) -> None:
        suffix = " ".join(str(item) for item in (subcommand, *args) if str(item))
        self.commands.append(f"CAP {suffix}")

    def add_global_handler(self, event: str, handler, priority: int = 0) -> None:
        del event, handler, priority
        return None

    def remove_global_handler(self, event: str, handler) -> None:
        del event, handler
        return None

    def process_data(self) -> None:
        return None

    def close(self) -> None:
        return None

    def reconnect(self) -> None:
        return None

    def set_keepalive(self, interval: int = 60) -> None:
        del interval
        return None

    def sasl_login(self, account: str, password: str) -> None:
        del account, password
        return None


class ReactorProxy:
    def __init__(self, connection: ConnectionProxy) -> None:
        self.connection = connection
        self.connections = [connection]

    @property
    def channels(self) -> ChannelMap:
        return self.connection.channels

    def server(self) -> ConnectionProxy:
        return self.connection

    def process_once(self, timeout: float = 0) -> None:
        del timeout
        return None

    def process_forever(self) -> None:
        return None

    def disconnect_all(self, message: str = "") -> None:
        self.connection.quit(message)


class BotProxy:
    def __init__(self, event: MessageEvent, args: str) -> None:
        self.event = event
        self.channel = event.channel or event.target
        self.sender = event.nickname
        self.nickname = event.nickname
        self.args = args

    def reply(self, text: str) -> None:
        print(text)

    def say(self, *args: str) -> None:
        if not args:
            return
        print(args[-1])

    def msg(self, *args: str) -> None:
        self.say(*args)

    def privmsg(self, *args: str) -> None:
        self.say(*args)


class GeneratedCommandStore:
    def __init__(
        self,
        state: JsonState,
        raw_irc_sender: Callable[[list[str]], str] | None = None,
    ):
        self.state = state
        self.raw_irc_sender = raw_irc_sender
        self._loaded: dict[str, LoadedCommand] = {}

    def handle(
        self,
        nick: str,
        target: str,
        text: str,
        enabled: Callable[[str], bool] | None = None,
        event: MessageEvent | None = None,
    ) -> list[str] | None:
        event = event or message_event(nick, target, text)
        for name, entry in self.entries():
            if enabled is not None and not enabled(name):
                continue
            command = self.load(name, entry)
            if command is None:
                continue
            match, toolbox_class = self.match_command(command, event)
            if not match:
                continue
            return self.run(command, match, nick, target, event, toolbox_class)
        return None

    def handle_event(
        self,
        event: MessageEvent,
        enabled: Callable[[str], bool] | None = None,
    ) -> list[GeneratedCommandReply]:
        replies: list[GeneratedCommandReply] = []
        for name, entry in self.entries():
            if enabled is not None and not enabled(name):
                continue
            command = self.load(name, entry)
            if command is None:
                continue
            match, toolbox_class = self.match_toolbox_command(command, event)
            if not match or toolbox_class is None:
                continue
            lines = self.run(
                command,
                match,
                event.nickname,
                event.channel or event.target,
                event,
                toolbox_class,
            )
            for target_name in output_targets(toolbox_class, event):
                replies.append(GeneratedCommandReply(target_name, lines))
        return replies

    def match_command(
        self,
        command: LoadedCommand,
        event: MessageEvent,
    ) -> tuple[re.Match[str] | None, type[Toolbox] | None]:
        match, toolbox_class = self.match_toolbox_command(command, event)
        if match:
            return match, toolbox_class
        if event.event_type not in {"pubmsg", "privmsg"}:
            return None, None
        return re.search(command.pattern, event.text), None

    def match_toolbox_command(
        self,
        command: LoadedCommand,
        event: MessageEvent,
    ) -> tuple[re.Match[str] | None, type[Toolbox] | None]:
        for toolbox_class in toolbox_classes(command.module):
            if not trigger_matches(toolbox_class, event.event_type):
                continue
            pattern = str(getattr(toolbox_class, "pattern", ""))
            if not pattern:
                continue
            match = re.search(pattern, event_field(event, str(getattr(toolbox_class, "match_field", "text"))))
            if match:
                return match, toolbox_class
        return None, None

    def reload(self, name: str | None = None) -> list[str]:
        if name:
            safe_name = safe_identifier(name)
            self._loaded.pop(safe_name, None)
            entry = self.state.data.setdefault("generated_commands", {}).get(safe_name)
            command = self.load(safe_name, entry) if isinstance(entry, dict) else None
            if command is None:
                return [f"No generated command named {safe_name}"]
            return ["reloaded:", f"- generated_commands.{safe_name}"]
        self._loaded.clear()
        loaded = []
        for command_name, entry in self.entries():
            if self.load(command_name, entry) is not None:
                loaded.append(f"- generated_commands.{command_name}")
        return ["reloaded:", *loaded] if loaded else ["no generated command modules found"]

    def entries(self) -> list[tuple[str, dict[str, Any]]]:
        root = self.state.data.setdefault("generated_commands", {})
        entries = [
            (str(name), entry)
            for name, entry in root.items()
            if isinstance(entry, dict) and entry.get("path")
        ]
        return sorted(entries)

    def command_entries(self) -> tuple[tuple[str, bool, str], ...]:
        rows = []
        for name, entry in self.entries():
            pattern = str(entry.get("pattern") or "")
            if not pattern:
                command = self.load(name, entry)
                pattern = command.pattern if command is not None else ""
            rows.append((name, True, pattern))
        return tuple(rows)

    def load(self, name: str, entry: dict[str, Any] | None) -> LoadedCommand | None:
        if not isinstance(entry, dict):
            return None
        safe_name = safe_identifier(name)
        path = generated_command_source_path(Path(str(entry.get("path", ""))))
        if not safe_name or path is None:
            return None
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return None
        loaded = self._loaded.get(safe_name)
        pattern = str(entry.get("pattern") or "")
        if loaded is not None and loaded.path == path and loaded.mtime == mtime:
            if pattern and loaded.pattern != pattern:
                loaded.pattern = pattern
            return loaded
        module_name = f"pyylmao_generated_{safe_name}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        configure_default_state(self.state)
        ircbot.set_irc_sender(self.raw_irc_sender)
        module.kv = KvContext(f"commands.{safe_name}", self.state)  # type: ignore[attr-defined]
        api = llm_api_module()
        api._pyylmao_state = self.state  # type: ignore[attr-defined]
        api._pyylmao_raw_irc_sender = self.raw_irc_sender  # type: ignore[attr-defined]
        module.llm = api  # type: ignore[attr-defined]
        module.irc_command = self.irc_command  # type: ignore[attr-defined]
        sys.modules[module_name] = module
        sys.modules["llm"] = api
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            return LoadedCommand(
                name=safe_name,
                path=path,
                pattern=pattern or r"$^",
                module=failed_module(traceback.format_exc(), repr(exc)),
                mtime=mtime,
            )
        if not pattern:
            pattern = str(getattr(module, "pattern", ""))
        if not pattern:
            classes = toolbox_classes(module)
            if classes:
                pattern = str(getattr(classes[0], "pattern", ""))
        if not pattern:
            return None
        command = LoadedCommand(safe_name, path, pattern, module, mtime)
        self._loaded[safe_name] = command
        return command

    def run(
        self,
        command: LoadedCommand,
        match: re.Match[str],
        nick: str,
        target: str,
        event: MessageEvent | None = None,
        toolbox_class: type[Toolbox] | None = None,
    ) -> list[str]:
        return self.run_with_args(command, list(match.groups()), nick, target, event, toolbox_class)

    def run_with_args(
        self,
        command: LoadedCommand,
        args: list[str],
        nick: str,
        target: str,
        event: MessageEvent | None = None,
        toolbox_class: type[Toolbox] | None = None,
    ) -> list[str]:
        event = event or message_event(nick, target, " ".join(str(item) for item in args))
        stdout = io.StringIO()
        stderr = io.StringIO()
        toolbox_class = toolbox_class or toolbox_class_for_direct_run(command)
        connection = ConnectionProxy(state=self.state, event=event) if toolbox_class is not None else None
        api = llm_api_module()
        api._pyylmao_state = self.state  # type: ignore[attr-defined]
        api._pyylmao_event = event  # type: ignore[attr-defined]
        api._pyylmao_raw_irc_sender = self.raw_irc_sender  # type: ignore[attr-defined]
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = self.invoke(command, args, event, toolbox_class, connection)
        except Exception:
            return traceback.format_exc().strip().splitlines()
        if connection is not None and connection.commands and self.raw_irc_sender is not None:
            with contextlib.suppress(Exception):
                self.raw_irc_sender(connection.commands)
        lines = stdout.getvalue().splitlines() + stderr.getvalue().splitlines()
        if result is not None:
            if isinstance(result, list):
                lines.extend(str(item) for item in result)
            else:
                lines.append(str(result))
        return lines or ["None"]

    def invoke(
        self,
        command: LoadedCommand,
        args: list[str],
        event: MessageEvent,
        toolbox_class: type[Toolbox] | None = None,
        connection: ConnectionProxy | None = None,
    ) -> Any:
        if toolbox_class is not None:
            return invoke_toolbox(toolbox_class, args, event, connection)

        entrypoint = getattr(command.module, "entrypoint", None)
        if callable(entrypoint):
            return invoke_callable(entrypoint, legacy_entrypoint_kwargs(args, event))

        arg_text = args_text(args)
        bot = BotProxy(event, arg_text)
        kwargs = command_callable_kwargs(arg_text, args, event, bot)
        run = getattr(command.module, "run", None)
        if callable(run):
            return invoke_callable(run, kwargs)
        command_callable = getattr(command.module, "command", None)
        if callable(command_callable):
            return invoke_callable(command_callable, kwargs)
        named_callable = getattr(command.module, f"{command.name}_command", None)
        if callable(named_callable):
            return invoke_callable(named_callable, kwargs)
        main_callable = getattr(command.module, "main", None)
        if callable(main_callable):
            return invoke_callable(main_callable, kwargs)
        if script_source_has_entrypoint(command.path):
            return invoke_script_source(command, args, event, self.state, self.raw_irc_sender)
        return f"generated command {command.name} has no entrypoint"

    def irc_command(self, command: str) -> str:
        commands = [line.strip() for line in str(command).splitlines() if line.strip()]
        if not commands:
            return ""
        if self.raw_irc_sender is None:
            return "\n".join(f"queued IRC command: {item}" for item in commands)
        return str(self.raw_irc_sender(commands))


def failed_module(error: str, summary: str = "") -> ModuleType:
    module = ModuleType("failed_generated_command")
    module._load_error = error  # type: ignore[attr-defined]
    module._load_error_summary = summary or error.strip().splitlines()[-1]  # type: ignore[attr-defined]

    def entrypoint(**_: Any) -> None:
        raise RuntimeError(error)

    module.entrypoint = entrypoint  # type: ignore[attr-defined]
    return module


def llm_api_module() -> ModuleType:
    existing = sys.modules.get("llm")
    if existing is not None and getattr(existing, "_pyylmao_api", False):
        return existing
    module = ModuleType("llm")
    module.Toolbox = Toolbox  # type: ignore[attr-defined]
    module.MessageEvent = MessageEvent  # type: ignore[attr-defined]
    module.Attachment = Attachment  # type: ignore[attr-defined]
    module.get_model = get_model  # type: ignore[attr-defined]
    module.model = get_model  # type: ignore[attr-defined]
    module.get_tools = get_tools  # type: ignore[attr-defined]
    module._pyylmao_api = True  # type: ignore[attr-defined]
    module.__all__ = ["Toolbox", "MessageEvent", "Attachment", "get_model", "model", "get_tools"]  # type: ignore[attr-defined]
    return module


class GeneratedLLMResponse:
    def __init__(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text


class GeneratedLLMModel:
    def __init__(self, model: str) -> None:
        self.model = normalize_generated_model_id(model)

    def prompt(
        self,
        prompt: Any,
        schema: Any = None,
        system: str | None = None,
        temperature: float | None = None,
        options: dict[str, Any] | None = None,
        attachments: Any = None,
        attachment: Any = None,
        **_: Any,
    ) -> GeneratedLLMResponse:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OpenRouter is not configured. Set OPENROUTER_API_KEY.")
        from .llm import OpenRouterClient

        text = str(prompt)
        if schema is not None:
            text = f"{text}\n\nReturn only JSON matching this schema:\n{schema_description(schema)}"
        prompt_options = options if isinstance(options, dict) else {}
        prompt_temperature = temperature
        if prompt_temperature is None and "temperature" in prompt_options:
            try:
                prompt_temperature = float(prompt_options["temperature"])
            except (TypeError, ValueError):
                prompt_temperature = None
        result = OpenRouterClient(api_key).chat(
            text,
            self.model,
            tools=None,
            temperature=prompt_temperature,
            extra_system=system or "",
            attachments=normalize_attachments(attachments, attachment),
        )
        return GeneratedLLMResponse("\n".join(result.lines))


def get_model(model: str) -> GeneratedLLMModel:
    return GeneratedLLMModel(str(model))


def get_tools(
    names: Any = None,
    enabled_only: bool = False,
    state: JsonState | None = None,
    **_: Any,
) -> GeneratedToolRegistry:
    from .tools_table import TOOL_INVENTORY, tool_enabled

    requested = normalize_tool_names(names)
    runtime_state = state
    api_module = sys.modules.get("llm")
    if runtime_state is None:
        runtime_state = getattr(api_module, "_pyylmao_state", None)
    event = getattr(api_module, "_pyylmao_event", None)
    raw_irc_sender = getattr(api_module, "_pyylmao_raw_irc_sender", None)
    tools: list[GeneratedTool] = []
    for name, plugin, _default in TOOL_INVENTORY:
        enabled = tool_enabled(name, runtime_state)
        if enabled_only and not enabled:
            continue
        if requested and name not in requested and f"default_api:{name}" not in requested:
            continue
        tools.append(
            GeneratedTool(
                name=name,
                plugin=plugin,
                enabled=enabled,
                state=runtime_state,
                event=event if isinstance(event, MessageEvent) else None,
                raw_irc_sender=raw_irc_sender,
            )
        )
    if runtime_state is not None:
        for name, pattern in generated_tool_entries(runtime_state):
            enabled = generated_command_enabled(name, runtime_state)
            if enabled_only and not enabled:
                continue
            if requested and name not in requested and f"default_api:{name}" not in requested:
                continue
            tools.append(
                GeneratedTool(
                    name=name,
                    plugin="pyylmao_generated_commands",
                    enabled=enabled,
                    kind="generated_command",
                    pattern=pattern,
                    state=runtime_state,
                    event=event if isinstance(event, MessageEvent) else None,
                    raw_irc_sender=raw_irc_sender,
                )
            )
    return GeneratedToolRegistry(tools)


def generated_tool_entries(state: JsonState) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    root = state.data.setdefault("generated_commands", {})
    for raw_name, entry in sorted(root.items()):
        safe_name = safe_identifier(str(raw_name))
        if not safe_name or not isinstance(entry, dict):
            continue
        path = generated_command_source_path(Path(str(entry.get("path", ""))))
        if path is None:
            continue
        pattern = str(entry.get("pattern") or "")
        if not pattern:
            try:
                pattern = infer_pattern_from_source(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pattern = ""
        rows.append((safe_name, pattern))
    return rows


def generated_command_enabled(name: str, state: JsonState) -> bool:
    try:
        from .triggers import TriggerStore

        return TriggerStore(state).enabled(name)
    except Exception:
        return True


def generated_tool_arguments(args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    if kwargs:
        return dict(kwargs)
    if len(args) == 1 and isinstance(args[0], dict):
        return dict(args[0])
    if len(args) == 1:
        return {"args": args[0]}
    if args:
        return {"args": list(args)}
    return {}


def infer_pattern_from_source(source: str) -> str:
    match = re.search(r"pattern\s*=\s*r?([\"'])(?P<pattern>.*?)(?<!\\)\1", source, flags=re.DOTALL)
    return match.group("pattern") if match else ""


def normalize_tool_names(names: Any = None) -> set[str]:
    if names is None:
        return set()
    if isinstance(names, str):
        raw_items = re.split(r"[\s,]+", names)
    else:
        try:
            raw_items = list(names)
        except TypeError:
            raw_items = [names]
    return {str(item).strip() for item in raw_items if str(item).strip()}


def normalize_attachments(attachments: Any = None, attachment: Any = None) -> list[Any] | None:
    items: list[Any] = []
    for value in (attachments, attachment):
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            items.extend(value)
        else:
            items.append(value)
    return items or None


def normalize_generated_model_id(model: str) -> str:
    stripped = model.strip()
    if stripped.startswith("openrouter/") and stripped.count("/") >= 2:
        return stripped[len("openrouter/") :]
    return stripped


def schema_description(schema: Any) -> str:
    annotations = getattr(schema, "__annotations__", None)
    if not isinstance(annotations, dict) or not annotations:
        return getattr(schema, "__name__", repr(schema))
    fields = []
    for name, value in annotations.items():
        field_type = getattr(value, "__name__", repr(value))
        fields.append(f"{name}: {field_type}")
    schema_name = getattr(schema, "__name__", "Schema")
    return f"{schema_name}({', '.join(fields)})"


def toolbox_classes(module: ModuleType) -> list[type[Toolbox]]:
    classes: list[type[Toolbox]] = []
    for value in module.__dict__.values():
        if not inspect.isclass(value) or value is Toolbox:
            continue
        try:
            if issubclass(value, Toolbox):
                classes.append(value)
        except TypeError:
            continue
    return classes


def trigger_matches(toolbox_class: type[Toolbox], event_type: str) -> bool:
    trigger_on = getattr(toolbox_class, "trigger_on", "pubmsg")
    if isinstance(trigger_on, str):
        triggers = {trigger_on}
    else:
        triggers = {str(item) for item in trigger_on}
    return event_type in triggers


def channel_map_from_state(state: JsonState | None, event: MessageEvent | None = None) -> ChannelMap:
    channels = ChannelMap()
    if state is not None:
        root = state.data.get("kvstore")
        if isinstance(root, dict):
            pyylmao_root = root.get("pyylmao")
            if isinstance(pyylmao_root, dict):
                irc_root = pyylmao_root.get("irc")
                if isinstance(irc_root, dict):
                    stored_channels = irc_root.get("channels")
                    if isinstance(stored_channels, dict):
                        for channel_name, entry in stored_channels.items():
                            users = entry.get("users") if isinstance(entry, dict) else None
                            channels[str(channel_name)] = Channel(str(channel_name), users)
    if event is not None:
        for channel_name in [event.channel, event.target, *event.channels]:
            if channel_name and str(channel_name).startswith("#"):
                channels.setdefault(str(channel_name), Channel(str(channel_name)))
    return channels


def normalize_channel_users(users: Any) -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    if isinstance(users, dict):
        iterable = users.items()
    elif isinstance(users, (list, tuple, set)):
        iterable = ((item, {}) for item in users)
    else:
        iterable = ()
    for nickname, metadata in iterable:
        clean = normalize_channel_user(str(nickname))
        if clean:
            rows.append((clean, metadata if isinstance(metadata, dict) else {}))
    return rows


def channel_user_key(channel: Channel, nickname: str) -> str | None:
    clean = normalize_channel_user(nickname)
    if clean in channel:
        return clean
    folded = clean.casefold()
    for key in channel:
        if str(key).casefold() == folded:
            return str(key)
    return None


def event_field(event: MessageEvent, field: str) -> str:
    return str(getattr(event, field, event.text))


def message_event(nick: str, target: str, text: str) -> MessageEvent:
    nickname = clean_nick(nick)
    channel = target if str(target).startswith("#") else ""
    event_type = "pubmsg" if channel else "privmsg"
    raw_line = f":{nickname}!@ PRIVMSG {target} :{text}"
    return MessageEvent(
        event_type=event_type,
        text=text,
        raw_line=raw_line,
        channel=channel,
        nickname=nickname,
        target=target,
    )


def output_targets(toolbox_class: type[Toolbox], event: MessageEvent) -> list[str]:
    send_to = getattr(toolbox_class, "send_to", None)
    if send_to is None or send_to == "":
        return default_output_targets(event)
    raw_targets = [send_to] if isinstance(send_to, str) else list(send_to)
    targets: list[str] = []
    for raw_target in raw_targets:
        target = str(raw_target).strip()
        if not target:
            continue
        if target in {"all", "*"}:
            targets.extend(all_channel_targets(event))
            continue
        if target in {"channel", "$channel"}:
            if event.channel:
                targets.append(event.channel)
            continue
        if target in {"target", "$target"}:
            if event.target:
                targets.append(event.target)
            continue
        if target in {"nick", "nickname", "sender", "$nick", "$nickname"}:
            if event.nickname:
                targets.append(event.nickname)
            continue
        targets.append(target)
    return dedupe_targets(targets)


def default_output_targets(event: MessageEvent) -> list[str]:
    if event.channel:
        return [event.channel]
    if event.event_type in {"privmsg", "notice", "ctcp", "invite"} and event.target:
        return [event.target]
    return []


def all_channel_targets(event: MessageEvent) -> list[str]:
    targets = list(event.channels)
    if event.channel:
        targets.append(event.channel)
    return dedupe_targets(targets)


def normalize_targets(targets) -> list[str]:
    if isinstance(targets, str):
        return [targets]
    try:
        return [str(target) for target in targets]
    except TypeError:
        return [str(targets)]


def dedupe_targets(targets: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for target in targets:
        if not target or target in seen:
            continue
        seen.add(target)
        deduped.append(target)
    return deduped


def invoke_toolbox(
    toolbox_class: type[Toolbox],
    args: list[str],
    event: MessageEvent,
    connection: ConnectionProxy | None = None,
) -> Any:
    connection = connection or ConnectionProxy()
    kwargs = {
        "event": event,
        "args": args,
        "channel": event.channel or event.target,
        "target": event.target,
        "nickname": event.nickname,
        "username": event.username,
        "hostname": event.hostname,
        "connection": connection,
        "irc_command": ircbot.irc_command,
    }
    instance = invoke_callable(toolbox_class, kwargs)
    for name, value in kwargs.items():
        if not hasattr(instance, name):
            with contextlib.suppress(Exception):
                setattr(instance, name, value)
    onload = getattr(instance, "_onload", None)
    if not callable(onload):
        return None
    return await_if_needed(onload())


def toolbox_class_for_direct_run(command: LoadedCommand) -> type[Toolbox] | None:
    if callable(getattr(command.module, "entrypoint", None)):
        return None
    if callable(getattr(command.module, "run", None)):
        return None
    if callable(getattr(command.module, "command", None)):
        return None
    if callable(getattr(command.module, f"{command.name}_command", None)):
        return None
    if callable(getattr(command.module, "main", None)):
        return None
    classes = toolbox_classes(command.module)
    return classes[0] if classes else None


def script_source_has_entrypoint(path: Path) -> bool:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return False
    if source.startswith("#!"):
        return True
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return False
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            if script_call_name(node.value) in {"print", "main"}:
                return True
        if isinstance(node, ast.If) and is_main_guard(node.test):
            return True
    return False


def script_call_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    return ""


def is_main_guard(node: ast.AST) -> bool:
    if not isinstance(node, ast.Compare):
        return False
    if not isinstance(node.left, ast.Name) or node.left.id != "__name__":
        return False
    if len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
        return False
    if len(node.comparators) != 1:
        return False
    comparator = node.comparators[0]
    return isinstance(comparator, ast.Constant) and comparator.value == "__main__"


def invoke_script_source(
    command: LoadedCommand,
    args: list[str],
    event: MessageEvent,
    state: JsonState,
    raw_irc_sender: Callable[[list[str]], str] | None,
) -> None:
    source = command.path.read_text(encoding="utf-8")
    api = llm_api_module()
    api._pyylmao_state = state  # type: ignore[attr-defined]
    api._pyylmao_event = event  # type: ignore[attr-defined]
    api._pyylmao_raw_irc_sender = raw_irc_sender  # type: ignore[attr-defined]
    globals_dict = {
        "__name__": "__main__",
        "__file__": str(command.path),
        "__package__": "",
        "args": args,
        "argv": args,
        "channel": event.channel or event.target,
        "sender": event.nickname,
        "nickname": event.nickname,
        "username": event.username,
        "hostname": event.hostname,
        "event": event,
        "text": event.text,
        "kv": KvContext(f"commands.{command.name}", state),
        "llm": api,
        "irc_command": ircbot.irc_command,
    }
    previous_argv = sys.argv
    try:
        sys.argv = [str(command.path), *[str(item) for item in args]]
        exec(compile(source, str(command.path), "exec"), globals_dict)
    finally:
        sys.argv = previous_argv


def legacy_entrypoint_kwargs(args: list[str], event: MessageEvent) -> dict[str, Any]:
    return {
        "args": args,
        "channel": event.channel or event.target,
        "nickname": event.nickname,
        "username": event.username,
        "hostname": event.hostname,
        "event": event,
        "text": event.text,
        "sender": event.nickname,
        "irc_command": ircbot.irc_command,
    }


def command_callable_kwargs(
    arg_text: str,
    argv: list[str],
    event: MessageEvent,
    bot: BotProxy,
) -> dict[str, Any]:
    return {
        "bot": bot,
        "args": arg_text,
        "argv": argv,
        "channel": event.channel or event.target,
        "sender": event.nickname,
        "nickname": event.nickname,
        "username": event.username,
        "hostname": event.hostname,
        "event": event,
        "text": event.text,
        "irc_command": ircbot.irc_command,
    }


def args_text(args: list[str]) -> str:
    if not args:
        return ""
    if len(args) == 1:
        return str(args[0])
    return " ".join(str(item) for item in args)


def invoke_callable(callable_obj: Callable[..., Any], values: dict[str, Any]) -> Any:
    try:
        signature = inspect.signature(callable_obj)
    except (TypeError, ValueError):
        return await_if_needed(callable_obj(**values))
    positional: list[Any] = []
    kwargs: dict[str, Any] = {}
    consumed: set[str] = set()
    accepts_var_keyword = False
    for parameter in signature.parameters.values():
        if parameter.kind == inspect.Parameter.VAR_KEYWORD:
            accepts_var_keyword = True
            continue
        if parameter.kind == inspect.Parameter.VAR_POSITIONAL:
            continue
        if parameter.name not in values:
            continue
        consumed.add(parameter.name)
        if parameter.kind == inspect.Parameter.POSITIONAL_ONLY:
            positional.append(values[parameter.name])
        else:
            kwargs[parameter.name] = values[parameter.name]
    if accepts_var_keyword:
        for name, value in values.items():
            if name not in consumed and name not in kwargs:
                kwargs[name] = value
    return await_if_needed(callable_obj(*positional, **kwargs))


def await_if_needed(value: Any) -> Any:
    if not inspect.isawaitable(value):
        return value
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(value)

    result: dict[str, Any] = {}
    error: dict[str, BaseException] = {}

    def runner() -> None:
        try:
            result["value"] = asyncio.run(value)
        except BaseException as exc:
            error["error"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()
    if error:
        raise error["error"]
    return result.get("value")


def safe_identifier(name: str) -> str:
    raw = str(name).strip().lower().replace("\\", "/").rsplit("/", 1)[-1]
    if raw.endswith(".py"):
        raw = raw[:-3]
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", raw).strip("_")
    return safe


def generated_command_source_path(path: Path) -> Path | None:
    if path.exists() and path.is_file():
        return path
    if path.exists() and path.is_dir():
        init_path = path / "__init__.py"
        if init_path.exists() and init_path.is_file():
            return init_path
    return None
