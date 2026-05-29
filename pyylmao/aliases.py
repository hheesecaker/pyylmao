from __future__ import annotations

import re
from collections.abc import Mapping

from .state import JsonState


DEFAULT_ALIASES: dict[str, str] = {
    "flash": "gemini/gemini-2.0-flash",
    "g": "openrouter/x-ai/grok-4.1-fast",
    "nano": "openrouter/openai/gpt-5-nano",
    "mini": "gpt-5-mini",
    "gpt5": "openrouter/openai/gpt-5",
    "banana": "openrouter/google/gemini-2.5-flash-image-preview",
    "hermes": "openrouter/nousresearch/hermes-4-405b",
    "sonoma": "openrouter/sonoma-sky-alpha",
    "gronk": "openrouter/x-ai/grok-3-mini-beta",
    "mistral": "openrouter/mistralai/mistral-small-24b-instruct-2501",
    "mini41": "openrouter/openai/gpt-4.1-mini",
    "nano41": "openrouter/openai/gpt-4.1-nano",
    "nano41o": "gpt-4.1-nano",
    "grok": "openrouter/x-ai/grok-4.1-fast",
    "gpt": "openrouter/openai/gpt-oss-120b",
    "gabe": "openrouter/x-ai/grok-3-mini-beta",
    "hy": "openrouter/tencent/hy3-preview",
    "hy2": "openrouter/tencent/hy3-preview",
    "sonnet": "openrouter/anthropic/claude-sonnet-4.5",
    "grok4": "openrouter/x-ai/grok-4-fast",
    "grok3": "openrouter/x-ai/grok-3",
    "gpt41": "gpt-4.1",
    "minimax": "openrouter/minimax/minimax-m2:free",
    "grox": "openrouter/x-ai/grok-3-mini-beta",
    "code": "openrouter/x-ai/grok-code-fast-1",
    "sherlock": "openrouter/openrouter/sherlock-think-alpha",
    "kimi": "openrouter/moonshotai/kimi-k2",
    "q": "openrouter/qwen/qwen3.6-plus:free",
    "dash": "openrouter/openrouter/sherlock-dash-alpha",
    "bert": "openrouter/openrouter/bert-nebulon-alpha",
    "pyylmao": "openrouter/x-ai/grok-4.1-fast",
    "chimera": "openrouter/tngtech/tng-r1t-chimera:free",
    "d": "openrouter/deepseek/deepseek-v3.2",
    "speciale": "openrouter/deepseek/deepseek-v3.2-speciale",
    "hunter": "openrouter/openrouter/hunter-alpha",
    "lite": "openrouter/google/gemini-3.1-flash-lite",
    "luna": "openrouter/sao10k/l3-lunaris-8b",
    "mm": "openrouter/minimax/minimax-m2.7",
    "nemo": "openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "nemo9": "openrouter/nvidia/nemotron-nano-9b-v2",
    "venice": "openrouter/cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
    "glm": "openrouter/z-ai/glm-4.7",
}

ALIAS_RE = re.compile(r"^[a-z0-9][a-z0-9_.:/-]*$", flags=re.IGNORECASE)


class AliasStore:
    def __init__(self, state: JsonState, defaults: Mapping[str, str] | None = None):
        self.state = state
        self.defaults = dict(DEFAULT_ALIASES if defaults is None else defaults)
        self.state.data.setdefault("llm_aliases", {})
        self.state.data.setdefault("llm_alias_deleted", [])

    def handle(self, text: str) -> list[str] | None:
        stripped = text.strip()
        lowered = stripped.lower()
        if lowered != "!alias" and not lowered.startswith("!alias "):
            return None
        parts = stripped.split()
        if len(parts) == 1:
            return alias_usage()

        command = parts[1].lower()
        if command in {"list", "list2"}:
            aliases = self.all_aliases()
            return [format_alias(name, model) for name, model in aliases.items()] or ["No aliases configured."]
        if command == "get":
            if len(parts) != 3:
                return ["Usage: !alias get <alias>"]
            name = normalize_alias(parts[2])
            model = self.get(name)
            if model is None:
                return [f"Alias '{name}' not found."]
            return [format_alias(name, model)]
        if command == "set":
            if len(parts) != 4:
                return ["Usage: !alias set <alias> <model_id>"]
            name = normalize_alias(parts[2])
            if not valid_alias_name(name):
                return [f"Invalid alias name: {parts[2]}"]
            model = parts[3].strip()
            self.set(name, model)
            return [f"Alias '{name}' set to '{model}'."]
        if command == "delete":
            if len(parts) != 3:
                return ["Usage: !alias delete <alias_name>"]
            name = normalize_alias(parts[2])
            if self.delete(name):
                return [f"Alias '{name}' removed."]
            return [f"Alias '{name}' not found."]
        if command == "get-default":
            return [f"Default model: '{self.default_model()}'"]
        if command == "set-default":
            if len(parts) != 3:
                return ["Usage: !alias set-default <model_id_or_alias>"]
            self.state.data["llm_default_alias"] = parts[2]
            self.state.save()
            return [f"Default model set to '{parts[2]}'."]

        return [
            f"Unknown command: '{command}'. Use list, get, set, delete, set-default, or get-default.",
            *alias_usage(),
        ]

    def all_aliases(self) -> dict[str, str]:
        deleted = set(self.state.data["llm_alias_deleted"])
        aliases = {name: model for name, model in self.defaults.items() if name not in deleted}
        aliases.update(
            {
                normalize_alias(name): str(model)
                for name, model in self.state.data["llm_aliases"].items()
                if str(model)
            }
        )
        return aliases

    def names(self) -> set[str]:
        return set(self.all_aliases())

    def get(self, name: str) -> str | None:
        return self.all_aliases().get(normalize_alias(name))

    def model_for(self, name: str, fallback: str | None = None) -> str | None:
        model = self.get(name)
        if model is None:
            return fallback
        return normalize_model_id(model)

    def set(self, name: str, model: str) -> None:
        normalized = normalize_alias(name)
        self.state.data["llm_aliases"][normalized] = model
        deleted = set(self.state.data["llm_alias_deleted"])
        deleted.discard(normalized)
        self.state.data["llm_alias_deleted"] = sorted(deleted)
        self.state.save()

    def delete(self, name: str) -> bool:
        normalized = normalize_alias(name)
        existed = self.get(normalized) is not None
        if not existed:
            return False
        self.state.data["llm_aliases"].pop(normalized, None)
        if normalized in self.defaults:
            deleted = set(self.state.data["llm_alias_deleted"])
            deleted.add(normalized)
            self.state.data["llm_alias_deleted"] = sorted(deleted)
        self.state.save()
        return True

    def default_model(self) -> str:
        configured = self.state.data.get("llm_default_alias")
        if configured:
            configured = str(configured)
            return self.get(configured) or configured
        return self.get("gpt") or DEFAULT_ALIASES["gpt"]


def alias_usage() -> list[str]:
    return [
        "Usage: !alias <command> [args]",
        "Commands:",
        "  list - List all aliases",
        "  get <alias> - Get the model for an alias",
        "  set <alias> <model_id> - Set an alias for a model",
        "  delete <alias_name> - Delete an alias",
        "  set-default <model_id_or_alias> - Set the default model",
        "  get-default - Get the current default model",
        "Example: !alias set myalias gpt-4",
        "Example: !alias get myalias",
    ]


def normalize_alias(name: str) -> str:
    return name.strip().lower()


def valid_alias_name(name: str) -> bool:
    return bool(ALIAS_RE.match(name))


def format_alias(name: str, model: str) -> str:
    return f"'{name}' -> '{model}'"


def normalize_model_id(model: str) -> str:
    model = model.strip()
    if model.startswith("openrouter/") and model.count("/") >= 2:
        return model[len("openrouter/") :]
    return model
