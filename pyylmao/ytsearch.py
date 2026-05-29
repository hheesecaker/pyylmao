from __future__ import annotations

import json
import os
import re
from html import unescape
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .link_preview import compact_count, youtube_logo


SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
DETAILS_URL = "https://www.googleapis.com/youtube/v3/videos"

YTSearchFetcher = Callable[[str, int], tuple[dict[str, Any], dict[str, Any]]]


class YTSearchError(Exception):
    pass


def is_ytsearch_command(text: str) -> bool:
    return re.match(r"^!yt (.+)$", text.strip(), flags=re.IGNORECASE) is not None


def render_ytsearch_command(
    text: str,
    fetcher: YTSearchFetcher | None = None,
    max_results: int = 5,
) -> list[str]:
    match = re.match(r"^!yt (.+)$", text.strip(), flags=re.IGNORECASE)
    if not match:
        return []
    query = match.group(1).strip()
    if not query:
        return ["Usage: !yt <query>"]
    limit = max(1, min(int(max_results), 25))
    search_data, details_data = (
        fetcher(query, limit) if fetcher is not None else fetch_youtube_search(query, limit)
    )
    return render_ytsearch_results(search_data, details_data, limit)


def fetch_youtube_search(query: str, max_results: int) -> tuple[dict[str, Any], dict[str, Any]]:
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        raise YTSearchError("YOUTUBE_API_KEY is not set")
    search = fetch_json(
        SEARCH_URL,
        {
            "part": "snippet",
            "type": "video",
            "maxResults": str(max_results),
            "q": query,
            "key": api_key,
        },
    )
    video_ids = search_video_ids(search)
    details = (
        fetch_json(
            DETAILS_URL,
            {
                "part": "contentDetails,statistics",
                "id": ",".join(video_ids),
                "key": api_key,
            },
        )
        if video_ids
        else {"items": []}
    )
    return search, details


def fetch_json(url: str, params: dict[str, str]) -> dict[str, Any]:
    request = Request(
        f"{url}?{urlencode(params)}",
        headers={"User-Agent": "pyylmao/ytsearch"},
    )
    with urlopen(request, timeout=20) as response:
        payload = response.read().decode("utf-8", errors="replace")
    data = json.loads(payload)
    return data if isinstance(data, dict) else {}


def render_ytsearch_results(
    search_data: dict[str, Any],
    details_data: dict[str, Any],
    max_results: int,
) -> list[str]:
    details = details_by_id(details_data)
    lines: list[str] = []
    for item in search_items(search_data)[:max_results]:
        video_id = search_video_id(item)
        if not video_id:
            continue
        snippet = item.get("snippet") if isinstance(item, dict) else None
        snippet = snippet if isinstance(snippet, dict) else {}
        detail = details.get(video_id, {})
        title = clean(snippet.get("title")) or "(untitled)"
        channel = clean(snippet.get("channelTitle"))
        duration = format_ytsearch_duration(nested_get(detail, "contentDetails", "duration"))
        views = compact_count(int_or_none(nested_get(detail, "statistics", "viewCount")))
        likes = compact_count(int_or_none(nested_get(detail, "statistics", "likeCount")))
        published = format_published(snippet.get("publishedAt") or snippet.get("publishTime"))
        description = clean(snippet.get("description"))

        first = f"{youtube_logo()} {title}"
        if channel:
            first += f" | {channel}"
        if duration:
            first += f" [{duration}]"
        if views:
            first += f" {views} views"
        if likes:
            first += f" {likes} likes"
        lines.append(truncate_irc_line(first))

        second_parts = []
        if published:
            second_parts.append(f"Published: {published}")
        if description:
            second_parts.append(description)
        second_parts.append(f"https://youtu.be/{video_id}")
        lines.append(truncate_irc_line("  " + " | ".join(second_parts)))

    return lines or ["No YouTube results found."]


def search_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    items = data.get("items")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def search_video_ids(data: dict[str, Any]) -> list[str]:
    return [video_id for item in search_items(data) for video_id in [search_video_id(item)] if video_id]


def search_video_id(item: dict[str, Any]) -> str:
    identifier = item.get("id")
    if isinstance(identifier, dict):
        return str(identifier.get("videoId") or "").strip()
    return ""


def details_by_id(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for item in search_items(data):
        video_id = str(item.get("id") or "").strip()
        if video_id:
            rows[video_id] = item
    return rows


def nested_get(data: dict[str, Any], *path: str) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def clean(value: Any) -> str:
    return unescape(str(value or "")).replace("\n", " ").strip()


def int_or_none(value: Any) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def format_published(value: Any) -> str:
    text = str(value or "")
    return text[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", text) else ""


def format_ytsearch_duration(value: Any) -> str:
    match = re.fullmatch(
        r"P(?:\d+D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?",
        str(value or ""),
    )
    if not match:
        return ""
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def truncate_irc_line(line: str, limit: int = 420) -> str:
    if len(line) <= limit:
        return line
    return line[: max(0, limit - 3)].rstrip() + "..."
