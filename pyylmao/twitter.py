from __future__ import annotations

import html
import json
import re
import textwrap
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


TWITTER_STATUS_RE = re.compile(
    r"(?:https?://)?(?:www\.)?"
    r"(?:twitter|x|xcancel|nitter)\.(?:com|net)/.+?/status/(\d+)",
    re.IGNORECASE,
)
TWITTER_COMMAND_RE = re.compile(r"^!twitter\s+(.+)$", re.IGNORECASE | re.DOTALL)
BARE_STATUS_RE = re.compile(r"(?<!\d)(\d{15,20})(?!\d)")
SYNDICATION_URL = "https://cdn.syndication.twimg.com/tweet-result"
LAST_JSON_PATHS = (
    Path("/usr/src/app/t.json"),
    Path("/app/t.json"),
    Path("/tmp/pyylmao-twitter-last.json"),
)


class TwitterCommandError(ValueError):
    pass


@dataclass(frozen=True)
class Tweet:
    status_id: str
    name: str = ""
    username: str = ""
    text: str = ""
    created_at: str = ""
    reply_count: int | None = None
    retweet_count: int | None = None
    like_count: int | None = None
    avatar_url: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


def is_twitter_command(text: str) -> bool:
    return status_id_from_text(text) is not None


def status_id_from_text(text: str) -> str | None:
    stripped = text.strip()
    command_match = TWITTER_COMMAND_RE.match(stripped)
    if command_match:
        stripped = command_match.group(1).strip()
    match = TWITTER_STATUS_RE.search(stripped)
    if match:
        return match.group(1)
    if command_match:
        bare_match = BARE_STATUS_RE.search(stripped)
        if bare_match:
            return bare_match.group(1)
    return None


def render_twitter_command(
    text: str,
    fetcher: Callable[[str], dict[str, Any]] | None = None,
) -> list[str]:
    status_id = status_id_from_text(text)
    if status_id is None:
        raise TwitterCommandError("Usage: !twitter <status-id-or-url>")
    data = (fetcher or fetch_tweet_json)(status_id)
    write_last_twitter_json(data)
    return render_tweet(tweet_from_json(status_id, data))


def fetch_tweet_json(status_id: str, timeout: float = 12.0) -> dict[str, Any]:
    query = urllib.parse.urlencode({"id": status_id, "lang": "en"})
    request = urllib.request.Request(
        f"{SYNDICATION_URL}?{query}",
        headers={"User-Agent": "pyylmao/0.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read(1_000_001)
    except OSError as exc:
        raise TwitterCommandError(f"twitter fetch failed: {exc}") from exc
    if len(payload) > 1_000_000:
        raise TwitterCommandError("twitter response too large")
    try:
        data = json.loads(payload.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise TwitterCommandError(f"twitter json decode failed: {exc}") from exc
    if not isinstance(data, dict):
        raise TwitterCommandError("twitter response was not an object")
    if "error" in data and not data.get("text"):
        raise TwitterCommandError(f"twitter error: {data.get('error')}")
    return data


def tweet_from_json(status_id: str, data: dict[str, Any]) -> Tweet:
    user = data.get("user")
    if not isinstance(user, dict):
        user = {}
    return Tweet(
        status_id=status_id,
        name=clean_tweet_text(first_text(data, "name") or first_text(user, "name")),
        username=clean_tweet_text(
            first_text(data, "screen_name", "username")
            or first_text(user, "screen_name", "username")
        ),
        text=clean_tweet_text(first_text(data, "text", "full_text", "tweet") or ""),
        created_at=format_tweet_date(first_text(data, "created_at", "createdAt", "date")),
        reply_count=first_int(data, "conversation_count", "reply_count", "replies"),
        retweet_count=first_int(data, "retweet_count", "retweets"),
        like_count=first_int(data, "favorite_count", "like_count", "likes"),
        avatar_url=first_text(user, "profile_image_url_https", "profile_image_url") or "",
        raw=data,
    )


def render_tweet(tweet: Tweet) -> list[str]:
    header = " ".join(
        item for item in [
            tweet.name or "(unknown)",
            f"@{tweet.username}" if tweet.username else "",
            tweet.created_at,
        ] if item
    )
    lines = [header]
    text = tweet.text or f"https://x.com/i/status/{tweet.status_id}"
    for paragraph in text.splitlines() or [text]:
        wrapped = textwrap.wrap(paragraph, width=92, replace_whitespace=False) or [""]
        lines.extend(wrapped)
    stats = render_tweet_stats(tweet)
    if stats:
        lines.append(stats)
    return lines


def render_tweet_stats(tweet: Tweet) -> str:
    parts = []
    if tweet.reply_count is not None:
        parts.append(f"💬 {tweet.reply_count}")
    if tweet.retweet_count is not None:
        parts.append(f"♻️ {tweet.retweet_count}")
    if tweet.like_count is not None:
        parts.append(f"❤️ {tweet.like_count}")
    return " ".join(parts)


def write_last_twitter_json(data: dict[str, Any]) -> None:
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    for path in LAST_JSON_PATHS:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(payload, encoding="utf-8")
            return
        except OSError:
            pass


def first_text(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if value is not None:
            return str(value)
    return ""


def first_int(data: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def clean_tweet_text(text: str) -> str:
    value = html.unescape(str(text))
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", "", value)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in value.split("\n")).strip()


def format_tweet_date(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            parsed = datetime.strptime(value, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.strftime("%b %d %Y")
        except ValueError:
            pass
    return value
