from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any, Callable

from .formatting import clean_nick
from .history_store import history_items
from .state import JsonState


pattern = r"^!seen (.+)$"


def is_seen_command(text: str) -> bool:
    return re.match(pattern, text.strip(), flags=re.IGNORECASE) is not None


def render_seen_command(
    text: str,
    state: JsonState,
    channel: str,
    nickname: str = "",
    *,
    now: Callable[[], float] = time.time,
) -> list[str]:
    match = re.match(pattern, text.strip(), flags=re.IGNORECASE)
    if not match:
        return ["Usage: !seen <nick>"]
    query = match.group(1).strip()
    if not query:
        return ["Usage: !seen <nick>"]

    current_nick = clean_nick(nickname)
    if current_nick and query.casefold() == current_nick.casefold():
        return [format_seen_line(current_nick, int(now()), text.strip())]

    item = last_seen_item(state, channel, query)
    if item is None:
        return [f"User {query} not found in history."]
    nick = str(item.get("nick") or item.get("nickname") or query)
    message = str(item.get("message") or item.get("me\u03df\u03dfage") or "")
    return [format_seen_line(nick, int(item.get("ts") or 0), message)]


def last_seen_item(state: JsonState, channel: str, query: str) -> dict[str, Any] | None:
    wanted = clean_nick(query).casefold()
    for item in reversed(history_items(state, channel)):
        nick = clean_nick(str(item.get("nick") or item.get("nickname") or ""))
        if nick.casefold() == wanted:
            return item
    return None


def format_seen_line(nickname: str, ts: int, message: str) -> str:
    when = datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"{nickname} was last seen pon {when} saying: {message}"


def entrypoint(args, channel, nickname, username, hostname):
    del username, hostname
    query = " ".join(str(arg) for arg in args).strip() if isinstance(args, list) else str(args).strip()
    from pyylmao.kv.backends.sqlite import default_root

    _, state = default_root()
    for line in render_seen_command(f"!seen {query}", state, channel, nickname):
        print(line)
