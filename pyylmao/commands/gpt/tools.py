from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from ...config import BotConfig
from ...generated_commands import get_tools as generated_get_tools
from ...llm_tools import LLMToolContext, LLMToolRegistry
from ...state import JsonState


def _api_module() -> Any:
    return sys.modules.get("llm")


def _runtime_state(state: JsonState | None = None) -> JsonState:
    if state is not None:
        return state
    api = _api_module()
    runtime_state = getattr(api, "_pyylmao_state", None)
    if isinstance(runtime_state, JsonState):
        return runtime_state
    state_path = Path(os.getenv("PYYLMAO_STATE", str(BotConfig.from_env().state_path)))
    return JsonState(state_path)


def _runtime_event() -> Any:
    return getattr(_api_module(), "_pyylmao_event", None)


def _raw_irc_sender() -> Any:
    return getattr(_api_module(), "_pyylmao_raw_irc_sender", None)


def _context(channel: str = "", state: JsonState | None = None) -> LLMToolContext:
    event = _runtime_event()
    target = str(
        channel
        or getattr(event, "channel", "")
        or getattr(event, "target", "")
        or "",
    )
    return LLMToolContext(target=target, history=(), state=_runtime_state(state))


def _registry(state: JsonState | None = None) -> LLMToolRegistry:
    runtime_state = _runtime_state(state)
    return LLMToolRegistry(runtime_state, raw_irc_sender=_raw_irc_sender())


def execute_tool(name: str, arguments: dict[str, Any] | None = None, **kwargs: Any) -> str:
    args = dict(arguments or {})
    args.update(kwargs)
    channel = str(args.pop("channel", "") or "")
    state = args.pop("state", None)
    runtime_state = state if isinstance(state, JsonState) else None
    return _registry(runtime_state).execute(_context(channel, runtime_state), name, args)


def read_command(name: str = "", **kwargs: Any) -> str:
    if not name and "name" in kwargs:
        name = str(kwargs.pop("name"))
    return execute_tool("read_command", {"name": name}, **kwargs)


def write_command(
    name: str = "",
    pattern: str = "",
    code: str = "",
    content: str = "",
    **kwargs: Any,
) -> str:
    arguments = {"name": name, "pattern": pattern, "code": code, "content": content}
    arguments.update(kwargs)
    return execute_tool("write_command", arguments)


def revise_pattern(name: str, pattern: str, **kwargs: Any) -> str:
    return execute_tool("revise_pattern", {"name": name, "pattern": pattern}, **kwargs)


def install_packages(packages: Any = None, **kwargs: Any) -> str:
    return execute_tool("install_packages", {"packages": packages}, **kwargs)


def run(command: str = "", cmd_name: str = "", args: Any = "", **kwargs: Any) -> str:
    arguments = {"command": command, "cmd_name": cmd_name, "args": args}
    arguments.update(kwargs)
    return execute_tool("run", arguments)


def eval(code: str = "", **kwargs: Any) -> str:
    return execute_tool("eval", {"code": code}, **kwargs)


def get_chat_history(
    channel: str = "",
    max_lines: Any = "100",
    include_bot: Any = "False",
    **kwargs: Any,
) -> str:
    arguments = {"channel": channel, "max_lines": max_lines, "include_bot": include_bot}
    arguments.update(kwargs)
    return execute_tool("get_chat_history", arguments)


def irc_command(command: str = "", **kwargs: Any) -> str:
    return execute_tool("irc_command", {"command": command}, **kwargs)


def channel_list(**kwargs: Any) -> str:
    return execute_tool("channel_list", {}, **kwargs)


def get_channel_users(channel: str = "", **kwargs: Any) -> str:
    return execute_tool("get_channel_users", {"channel": channel}, **kwargs)


def llm_version(**kwargs: Any) -> str:
    return execute_tool("llm_version", {}, **kwargs)


def llm_time(**kwargs: Any) -> str:
    return execute_tool("llm_time", {}, **kwargs)


def read_skill(name: str, **kwargs: Any) -> str:
    return execute_tool("read_skill", {"name": name}, **kwargs)


def list_skills(**kwargs: Any) -> str:
    return execute_tool("list_skills", {}, **kwargs)


def create_skill(name: str, content: str, **kwargs: Any) -> str:
    return execute_tool("create_skill", {"name": name, "content": content}, **kwargs)


def query_skills(query: str, **kwargs: Any) -> str:
    return execute_tool("query_skills", {"query": query}, **kwargs)


def query_skill(query: str, **kwargs: Any) -> str:
    return query_skills(query, **kwargs)


def update_skill(name: str, content: str, **kwargs: Any) -> str:
    return execute_tool("update_skill", {"name": name, "content": content}, **kwargs)


def remember(text: str = "", memories: Any = None, **kwargs: Any) -> str:
    arguments = {"text": text}
    if memories is not None:
        arguments["memories"] = memories
    arguments.update(kwargs)
    return execute_tool("remember", arguments)


def forget(query: str = "", keys: Any = None, **kwargs: Any) -> str:
    arguments = {"query": query}
    if keys is not None:
        arguments["keys"] = keys
    arguments.update(kwargs)
    return execute_tool("forget", arguments)


def search_memories(queries: Any, **kwargs: Any) -> str:
    return execute_tool("search_memories", {"queries": queries}, **kwargs)


def semantic_search(query: str = "", phrases: Any = "", profile: str = "", **kwargs: Any) -> str:
    arguments = {"query": query, "phrases": phrases, "profile": profile}
    arguments.update(kwargs)
    return execute_tool("semantic_search", arguments)


def save_artifact(
    filename: str = "",
    contents: str = "",
    content: str = "",
    create_dirs: Any = "",
    **kwargs: Any,
) -> str:
    arguments = {
        "filename": filename,
        "contents": contents,
        "content": content,
        "create_dirs": create_dirs,
    }
    arguments.update(kwargs)
    return execute_tool("save_artifact", arguments)


def read_artifact(filename: str, **kwargs: Any) -> str:
    return execute_tool("read_artifact", {"filename": filename}, **kwargs)


def list_artifacts(subdir: str = "", **kwargs: Any) -> str:
    return execute_tool("list_artifacts", {"subdir": subdir}, **kwargs)


def list_artifact(subdir: str = "", **kwargs: Any) -> str:
    return list_artifacts(subdir, **kwargs)


def get_tools(
    names: Any = None,
    enabled_only: bool = False,
    state: JsonState | None = None,
    **kwargs: Any,
) -> Any:
    runtime_state = _runtime_state(state)
    return generated_get_tools(names=names, enabled_only=enabled_only, state=runtime_state, **kwargs)


def get_enabled_tools(names: Any = None, **kwargs: Any) -> Any:
    return get_tools(names=names, enabled_only=True, **kwargs)


__all__ = [
    "channel_list",
    "create_skill",
    "eval",
    "execute_tool",
    "forget",
    "get_channel_users",
    "get_chat_history",
    "get_enabled_tools",
    "get_tools",
    "install_packages",
    "irc_command",
    "list_artifact",
    "list_artifacts",
    "list_skills",
    "llm_time",
    "llm_version",
    "query_skill",
    "query_skills",
    "read_artifact",
    "read_command",
    "read_skill",
    "remember",
    "revise_pattern",
    "run",
    "save_artifact",
    "search_memories",
    "semantic_search",
    "update_skill",
    "write_command",
]
