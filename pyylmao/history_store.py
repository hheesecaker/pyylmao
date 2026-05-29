from __future__ import annotations

import time
from typing import Any

from .state import JsonState


MAX_HISTORY_ITEMS = 20000
BOT_NICK = "pyylmao"
USER_MODE_PREFIXES = "~&@%+"


def _dict_at(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        value = {}
        parent[key] = value
    return value


def _list_at(parent: dict[str, Any], key: str) -> list[Any]:
    value = parent.get(key)
    if not isinstance(value, list):
        value = []
        parent[key] = value
    return value


def pyylmao_root(state: JsonState) -> dict[str, Any]:
    kv_root = _dict_at(state.data, "kvstore")
    root = _dict_at(kv_root, "pyylmao")
    _list_at(root, "_history")
    irc = _dict_at(root, "irc")
    _dict_at(irc, "channels")
    return root


def channel_entry(state: JsonState, channel: str) -> dict[str, Any]:
    root = pyylmao_root(state)
    irc = _dict_at(root, "irc")
    channels = _dict_at(irc, "channels")
    entry = _dict_at(channels, channel)
    _list_at(entry, "history")
    return entry


def channel_history(state: JsonState, channel: str) -> list[Any]:
    return _list_at(channel_entry(state, channel), "history")


def normalize_channel_user(nickname: str) -> str:
    return str(nickname).strip().lstrip(USER_MODE_PREFIXES)


def channel_users(state: JsonState, channel: str) -> dict[str, Any]:
    entry = channel_entry(state, channel)
    return coerce_users_dict(entry)


def coerce_users_dict(entry: dict[str, Any]) -> dict[str, Any]:
    users = entry.get("users")
    if isinstance(users, dict):
        return users
    normalized: dict[str, Any] = {}
    if isinstance(users, list):
        for nickname in users:
            clean = normalize_channel_user(str(nickname))
            if clean:
                normalized[clean] = {}
    entry["users"] = normalized
    return normalized


def set_channel_users(state: JsonState, channel: str, nicknames: list[str]) -> None:
    users = channel_users(state, channel)
    users.clear()
    for nickname in nicknames:
        clean = normalize_channel_user(nickname)
        if clean:
            users[clean] = {}
    state.save()


def add_channel_users(state: JsonState, channel: str, nicknames: list[str]) -> None:
    users = channel_users(state, channel)
    for nickname in nicknames:
        clean = normalize_channel_user(nickname)
        if clean:
            users.setdefault(clean, {})
    state.save()


def remove_channel_user(state: JsonState, channel: str, nickname: str) -> None:
    users = channel_users(state, channel)
    remove_user_key(users, nickname)
    state.save()


def remove_user_from_all_channels(state: JsonState, nickname: str) -> None:
    channels = _dict_at(_dict_at(pyylmao_root(state), "irc"), "channels")
    for entry in channels.values():
        if isinstance(entry, dict) and isinstance(entry.get("users"), (dict, list)):
            remove_user_key(coerce_users_dict(entry), nickname)
    state.save()


def rename_user_in_all_channels(state: JsonState, old_nickname: str, new_nickname: str) -> None:
    new_clean = normalize_channel_user(new_nickname)
    if not new_clean:
        return
    channels = _dict_at(_dict_at(pyylmao_root(state), "irc"), "channels")
    for entry in channels.values():
        if not isinstance(entry, dict) or not isinstance(entry.get("users"), (dict, list)):
            continue
        users = coerce_users_dict(entry)
        if remove_user_key(users, old_nickname):
            users[new_clean] = {}
    state.save()


def remove_user_key(users: dict[str, Any], nickname: str) -> bool:
    clean = normalize_channel_user(nickname)
    if clean in users:
        del users[clean]
        return True
    folded = clean.casefold()
    for key in list(users):
        if key.casefold() == folded:
            del users[key]
            return True
    return False


def history_items(state: JsonState, channel: str) -> list[dict[str, Any]]:
    return [item for item in channel_history(state, channel) if isinstance(item, dict)]


def record_history(
    state: JsonState,
    channel: str,
    nickname: str,
    message: str,
    *,
    role: str = "user",
    username: str = "",
    hostname: str = "",
    model: str | None = None,
    ts: int | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "ts": int(time.time()) if ts is None else ts,
        "role": role,
        "channel": channel,
        "nickname": nickname,
        "username": username,
        "hostname": hostname,
        "message": message,
    }
    if model:
        item["model"] = model

    root = pyylmao_root(state)
    global_history = _list_at(root, "_history")
    local_history = channel_history(state, channel)
    global_history.append(item)
    local_history.append(item)
    trim_history(global_history)
    trim_history(local_history)
    state.save()
    return item


def trim_history(items: list[Any], max_items: int = MAX_HISTORY_ITEMS) -> None:
    overflow = len(items) - max_items
    if overflow > 0:
        del items[:overflow]


def clear_channel_history(state: JsonState, channel: str) -> None:
    channel_history(state, channel).clear()
    state.save()
