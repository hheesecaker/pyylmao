from __future__ import annotations

from typing import Any

from ...aliases import DEFAULT_ALIASES, AliasStore, normalize_model_id
from ...generated_commands import Attachment, get_model, get_tools
from ...llm import LLMResult, OpenRouterClient, format_cents, format_model_name, stats_line
from ...llm_tools import format_tool_args, parse_tool_arguments
from ...router import LLMOptions, parse_llm_options, parse_llm_prompt
from ...state import JsonState


def resolve_model(
    key: str,
    state: JsonState | None = None,
    *,
    default_model: str = "openai/gpt-oss-120b",
    grok_model: str = "x-ai/grok-4.1-fast",
) -> str:
    aliases = AliasStore(state) if state is not None else None
    name = str(key).strip()
    if aliases is not None:
        if name == "gpt":
            return normalize_model_id(aliases.default_model())
        resolved = aliases.model_for(name)
        if resolved is not None:
            return resolved
    default_alias = DEFAULT_ALIASES.get(name.lower())
    if default_alias is not None:
        return normalize_model_id(default_alias)
    if name == "gpt":
        return default_model
    if name == "grok":
        return grok_model
    return normalize_model_id(name)


def parse_prompt(text: str, aliases: set[str] | None = None) -> tuple[str, str] | None:
    return parse_llm_prompt(text, aliases)


def parse_options(prompt: str) -> tuple[str, LLMOptions]:
    return parse_llm_options(prompt)


def model_from_trigger(trigger: str, state: JsonState | None = None, **kwargs: Any) -> str:
    return resolve_model(trigger, state, **kwargs)


__all__ = [
    "AliasStore",
    "Attachment",
    "DEFAULT_ALIASES",
    "LLMOptions",
    "LLMResult",
    "OpenRouterClient",
    "format_cents",
    "format_model_name",
    "format_tool_args",
    "get_model",
    "get_tools",
    "model_from_trigger",
    "normalize_model_id",
    "parse_llm_options",
    "parse_llm_prompt",
    "parse_options",
    "parse_prompt",
    "parse_tool_arguments",
    "resolve_model",
    "stats_line",
]
