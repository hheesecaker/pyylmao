from __future__ import annotations

import re

from .state import JsonState


TOOLS: tuple[tuple[str, str, str], ...] = (
    ("install_packages", "llm_cmd_tools", "Yes"),
    ("read_command", "llm_cmd_tools", "Yes"),
    ("write_command", "llm_cmd_tools", "Yes"),
    ("revise_pattern", "llm_cmd_tools", "Yes"),
    ("run", "llm_run_command", "Yes"),
    ("irc_command", "llm_irc_tools", "Yes"),
    ("get_chat_history", "llm_irc_tools", "Yes"),
    ("read_skill", "llm_skill_tools", "Yes"),
    ("list_skills", "llm_skill_tools", "Yes"),
    ("create_skill", "llm_skill_tools", "Yes"),
    ("remember", "llm_memory_tools", "Yes"),
    ("forget", "llm_memory_tools", "Yes"),
    ("search_memories", "llm_memory_tools", "Yes"),
    ("semantic_search", "llm_web_search", "Yes"),
    ("list_artifacts", "llm_artifact_tools", "Yes"),
    ("eval", "llm_eval_tool", "No"),
    ("channel_list", "llm_irc_tools", "No"),
    ("get_channel_users", "llm_irc_tools", "No"),
    ("llm_version", "llm.default_plugins.default_tools", "No"),
    ("llm_time", "llm.default_plugins.default_tools", "No"),
    ("query_skills", "llm_skill_tools", "No"),
    ("update_skill", "llm_skill_tools", "No"),
)


HIDDEN_TOOL_INVENTORY: tuple[tuple[str, str, str], ...] = (
    ("save_artifact", "llm_artifact_tools", "Yes"),
    ("read_artifact", "llm_artifact_tools", "Yes"),
)


TOOL_INVENTORY: tuple[tuple[str, str, str], ...] = (
    *TOOLS[:14],
    *HIDDEN_TOOL_INVENTORY,
    *TOOLS[14:],
)


def render_tools_table(state: JsonState | None = None) -> list[str]:
    rows = [format_tools_row("tool_name", "plugin", "enabled")]
    rows.extend(
        format_tools_row(tool_name, plugin, "Yes" if tool_enabled(tool_name, state) else "No")
        for tool_name, plugin, _ in TOOLS
    )
    return [
        "",
        "                                                                    ",
        *rows,
        "🮝🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮟 🮝🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮘🮟 🮝🮘🮘🮘🮘🮘🮘🮘🮘🮟",
    ]


def format_tools_row(tool_name: str, plugin: str, enabled: str) -> str:
    return f" {tool_name:<17} 🭍  {plugin:<33} 🭍  {enabled:<7} 🭍"


def handle_tool_toggle(text: str, state: JsonState) -> list[str] | None:
    match = re.match(r"^([+-])tools?\s+(.+)$", text.strip(), flags=re.IGNORECASE)
    if not match:
        return None
    sign, raw_tokens = match.groups()
    enabled = sign == "+"
    tokens = [token for token in raw_tokens.split() if token]
    if not tokens:
        return None
    statuses = state.data.setdefault("llm_tool_enabled", {})
    for token in tokens:
        name = canonical_tool_name(token)
        if name:
            statuses[name] = enabled
    state.save()
    heading = "enabled:" if enabled else "disabled:"
    return [heading, *[f"✔ {token}" for token in tokens]]


def tool_enabled(name: str, state: JsonState | None = None) -> bool:
    canonical = canonical_tool_name(name)
    if state is not None:
        statuses = state.data.setdefault("llm_tool_enabled", {})
        if canonical in statuses:
            return bool(statuses[canonical])
    for tool_name, _, default in TOOL_INVENTORY:
        if canonical_tool_name(tool_name) == canonical:
            return default == "Yes"
    return True


def canonical_tool_name(name: str) -> str:
    canonical = name.strip().lower().lstrip("+-!")
    aliases = {
        "list_artifact": "list_artifacts",
        "query_skill": "query_skills",
    }
    return aliases.get(canonical, canonical)
