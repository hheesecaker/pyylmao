from __future__ import annotations

import asyncio
import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Awaitable, Callable, Protocol

from .filters import FilterStore
from .state import JsonState


PUBLIC_APPVIEW = "https://api.bsky.app"
SEARCH_PATH = "/xrpc/app.bsky.feed.searchPosts"


class BlueskyError(RuntimeError):
    pass


@dataclass(frozen=True)
class BlueskyPost:
    uri: str
    handle: str
    text: str
    created_at: str | None = None

    @property
    def web_url(self) -> str:
        rkey = self.uri.rstrip("/").rsplit("/", 1)[-1]
        return f"https://bsky.app/profile/{self.handle}/post/{rkey}"


class BlueskySearchClient(Protocol):
    def search_posts(self, query: str, limit: int = 25) -> list[BlueskyPost]:
        ...


class PublicBlueskyClient:
    def __init__(self, host: str = PUBLIC_APPVIEW, timeout: float = 15.0):
        self.host = host.rstrip("/")
        self.timeout = timeout

    def search_posts(self, query: str, limit: int = 25) -> list[BlueskyPost]:
        params = urllib.parse.urlencode(
            {"q": query, "limit": max(1, min(limit, 100)), "sort": "latest"}
        )
        request = urllib.request.Request(
            f"{self.host}{SEARCH_PATH}?{params}",
            headers={"User-Agent": "pyylmao/0.1"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except OSError as exc:
            raise BlueskyError(f"Bluesky search failed: {exc}") from exc
        return [post for item in payload.get("posts", []) if (post := parse_post_view(item))]


class BlueskyFeedWatcher:
    def __init__(
        self,
        filters: FilterStore,
        state: JsonState,
        client: BlueskySearchClient | None = None,
        poll_seconds: float = 60.0,
        search_limit: int = 25,
        max_seen: int = 2000,
    ):
        self.filters = filters
        self.state = state
        self.client = client or PublicBlueskyClient()
        self.poll_seconds = poll_seconds
        self.search_limit = search_limit
        self.max_seen = max_seen
        self.state.data.setdefault("bluesky_seen", [])

    async def run(
        self,
        send: Callable[[str, list[str]], Awaitable[None]],
        target: str,
    ) -> None:
        await send(target, ["🤖 Bot is listening"])
        while True:
            started = time.monotonic()
            for lines in await asyncio.to_thread(self.poll_once):
                await send(target, lines)
            elapsed = time.monotonic() - started
            await asyncio.sleep(max(1.0, self.poll_seconds - elapsed))

    def poll_once(self) -> list[list[str]]:
        patterns = self.filters.patterns()
        if not patterns:
            return []
        seen_list = list(self.state.data.setdefault("bluesky_seen", []))
        seen = set(seen_list)
        messages: list[list[str]] = []
        for pattern in patterns:
            query = search_query_for_pattern(pattern)
            if not query:
                continue
            try:
                posts = self.client.search_posts(query, self.search_limit)
            except BlueskyError:
                continue
            for post in posts:
                if post.uri in seen:
                    continue
                if not post_matches(pattern, post):
                    continue
                seen.add(post.uri)
                seen_list.append(post.uri)
                messages.append(format_post(post))
        if messages:
            self.state.data["bluesky_seen"] = seen_list[-self.max_seen :]
            self.state.save()
        return messages


def parse_post_view(item: dict) -> BlueskyPost | None:
    uri = str(item.get("uri") or "")
    author = item.get("author") or {}
    handle = str(author.get("handle") or "")
    record = item.get("record") or {}
    text = str(record.get("text") or item.get("text") or "")
    created_at = record.get("createdAt")
    if not uri or not handle:
        return None
    return BlueskyPost(uri=uri, handle=handle, text=text, created_at=created_at)


def post_matches(pattern: str, post: BlueskyPost) -> bool:
    try:
        compiled = re.compile(pattern)
    except re.error:
        return False
    haystack = f"{post.text}\n{post.web_url}"
    return compiled.search(haystack) is not None


def format_post(post: BlueskyPost) -> list[str]:
    text = post.text.strip()
    if not text:
        return [post.web_url]
    lines = text.splitlines()
    lines[-1] = f"{lines[-1]} {post.web_url}"
    return lines


def search_query_for_pattern(pattern: str) -> str:
    stripped = pattern.strip()
    if not stripped:
        return ""
    cleaned = re.sub(r"\(\?[aiLmsux-]+:?", "", stripped)
    cleaned = re.sub(r"\\([.\\+*?\[\]^$(){}=!<>|:-])", r"\1", cleaned)
    cleaned = re.sub(r"[^\w\s@#.'-]+", " ", cleaned)
    terms = [term for term in cleaned.split() if len(term) >= 2]
    if not terms:
        return stripped[:64]
    return " ".join(terms[:6])[:128]
