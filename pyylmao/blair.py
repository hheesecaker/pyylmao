from __future__ import annotations

import html
import json
import pprint
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser


LIGMA_BASE_URL = "https://ligma.pro"
R000T_ACCOUNT_ID = "1"
DEFAULT_LIMIT = 12


class BlairCommandError(ValueError):
    pass


@dataclass(frozen=True)
class BlairPost:
    id: str
    content: str
    created_at: str
    replies_count: int
    url: str


@dataclass(frozen=True)
class BlairReply:
    content: str


class MastodonClient:
    def __init__(self, base_url: str = LIGMA_BASE_URL):
        self.base_url = base_url.rstrip("/")

    def pinned_posts(self, limit: int = DEFAULT_LIMIT) -> list[BlairPost]:
        query = urllib.parse.urlencode({"pinned": "true", "limit": str(limit)})
        payload = self._get_json(
            f"/api/v1/accounts/{R000T_ACCOUNT_ID}/statuses?{query}"
        )
        if not isinstance(payload, list):
            raise BlairCommandError("Unexpected Mastodon statuses response")
        return [parse_post(item) for item in payload[:limit] if isinstance(item, dict)]

    def replies(self, status_id: str, limit: int = 3) -> list[BlairReply]:
        payload = self._get_json(f"/api/v1/statuses/{status_id}/context")
        descendants = payload.get("descendants") if isinstance(payload, dict) else None
        if not isinstance(descendants, list):
            return []
        replies: list[BlairReply] = []
        for item in descendants:
            if isinstance(item, dict):
                replies.append(BlairReply(content=str(item.get("content") or "")))
            if len(replies) >= limit:
                break
        return replies

    def _get_json(self, path: str):
        request = urllib.request.Request(
            self.base_url + path,
            headers={
                "Accept": "application/json",
                "User-Agent": "pyylmao/0.1",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise BlairCommandError(f"Lookup failed: {exc.code} - {detail[:240]}") from exc
        except OSError as exc:
            raise BlairCommandError(f"Lookup failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise BlairCommandError(f"Could not decode Mastodon response: {exc}") from exc


def is_blair_command(text: str) -> bool:
    return text.strip().lower() == "!blair"


def is_blair2_command(text: str) -> bool:
    stripped = text.strip().lower()
    return stripped == "!blair2" or stripped.startswith("!blair2 ")


def render_blair_command(text: str, client: MastodonClient | None = None) -> list[str]:
    if not is_blair_command(text):
        return ["Usage: !blair"]
    client = client or MastodonClient()
    posts = client.pinned_posts(DEFAULT_LIMIT)
    lines = ["Posts from @r000t@ligma.pro (up to 12):"]
    for index, post in enumerate(posts, start=1):
        lines.extend(["", f"Post {index}:"])
        content_lines = html_to_text(post.content).splitlines() or [""]
        lines.extend(content_lines)
        lines.append(f"Replies: {post.replies_count}")
        replies = client.replies(post.id) if index <= 3 and post.replies_count else []
        for reply in replies[:3]:
            reply_text = html_to_text(reply.content)
            reply_lines = reply_text.splitlines() or [""]
            lines.append("  Reply: " + reply_lines[0])
            lines.extend(reply_lines[1:])
    return lines


def render_blair2_command(text: str, client: MastodonClient | None = None) -> list[str]:
    if not is_blair2_command(text):
        return ["Usage: !blair2"]
    client = client or MastodonClient()
    posts = client.pinned_posts(DEFAULT_LIMIT)
    lines = ["Posts from @r000t@ligma.pro (up to 12):"]
    for index, post in enumerate(posts, start=1):
        lines.extend(["", f"Post {index}:"])
        lines.extend(pprint.pformat(post.content, width=76).splitlines())
        lines.append(f"Replies: {post.replies_count}")
    return lines


def parse_post(item: dict) -> BlairPost:
    return BlairPost(
        id=str(item.get("id") or ""),
        content=str(item.get("content") or ""),
        created_at=str(item.get("created_at") or ""),
        replies_count=_int(item.get("replies_count")),
        url=str(item.get("url") or item.get("uri") or ""),
    )


def html_to_text(value: str) -> str:
    parser = MastodonHTMLParser()
    parser.feed(value)
    parser.close()
    text = parser.text()
    text = re.sub(r"[ \t]+\n", "\n", text)
    return html.unescape(text).strip()


class MastodonHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.href_stack: list[str | None] = []

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        if tag in {"p", "br"}:
            self._newline()
        if tag == "a":
            href = None
            for name, value in attrs:
                if name.lower() == "href":
                    href = value
                    break
            self.href_stack.append(href)

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag == "a":
            href = self.href_stack.pop() if self.href_stack else None
            if href and href.startswith("http"):
                current = "".join(self.parts).rstrip()
                if not current.endswith(f"({href})"):
                    self.parts.append(f" ({href})")
        if tag == "p":
            self._newline()

    def handle_data(self, data: str):
        self.parts.append(data)

    def text(self) -> str:
        lines = [re.sub(r"\s+", " ", line).strip() for line in "".join(self.parts).splitlines()]
        return "\n".join(line for line in lines if line)

    def _newline(self) -> None:
        if self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")


def _int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
