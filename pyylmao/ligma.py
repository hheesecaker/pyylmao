from __future__ import annotations

import html
import json
import re
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Callable

from .nostr import merge_avatar_and_text, render_avatar_lines


pattern = r"^.*ligma\.pro/@[^/]+/(\d+)\s?(.*)$"

LIGMA_BASE_URL = "https://ligma.pro"
LIGMA_STATUS_RE = re.compile(pattern, re.IGNORECASE | re.DOTALL)


class LigmaCommandError(ValueError):
    pass


@dataclass(frozen=True)
class LigmaRequest:
    status_id: str
    show_all: bool = False


@dataclass(frozen=True)
class LigmaStatus:
    id: str
    content: str
    created_at: str = ""
    display_name: str = ""
    username: str = ""
    avatar_url: str = ""
    replies_count: int = 0
    reblogs_count: int = 0
    favourites_count: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


class LigmaClient:
    def __init__(self, base_url: str = LIGMA_BASE_URL):
        self.base_url = base_url.rstrip("/")

    def status(self, status_id: str) -> LigmaStatus:
        payload = self._get_json(f"/api/v1/statuses/{urllib.parse.quote(status_id)}")
        if not isinstance(payload, dict):
            raise LigmaCommandError("Unexpected ligma status response")
        return status_from_json(payload)

    def replies(self, status_id: str) -> list[LigmaStatus]:
        payload = self._get_json(f"/api/v1/statuses/{urllib.parse.quote(status_id)}/context")
        descendants = payload.get("descendants") if isinstance(payload, dict) else None
        if not isinstance(descendants, list):
            return []
        return [status_from_json(item) for item in descendants if isinstance(item, dict)]

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
            raise LigmaCommandError(f"Lookup failed: {exc.code} - {detail[:240]}") from exc
        except OSError as exc:
            raise LigmaCommandError(f"Lookup failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise LigmaCommandError(f"Could not decode Mastodon response: {exc}") from exc


def is_ligma_command(text: str) -> bool:
    return bool(LIGMA_STATUS_RE.match(text.strip()))


def render_ligma_command(
    text: str,
    client: LigmaClient | None = None,
    avatar_renderer: Callable[[str], list[str]] | None = None,
) -> list[str]:
    request = parse_ligma_request(text)
    client = client or LigmaClient()
    status = client.status(request.status_id)
    lines = render_ligma_status(status, avatar_renderer=avatar_renderer)
    if request.show_all:
        for reply in client.replies(request.status_id):
            lines.extend(indent_lines(render_ligma_status(reply, avatar_renderer=avatar_renderer), "        "))
    return lines


def parse_ligma_request(text: str) -> LigmaRequest:
    match = LIGMA_STATUS_RE.match(text.strip())
    if match is None:
        raise LigmaCommandError("Usage: https://ligma.pro/@user/<status-id> [all]")
    status_id, rest = match.groups()
    return LigmaRequest(status_id=status_id, show_all="all" in rest.lower().split())


def status_from_json(data: dict[str, Any]) -> LigmaStatus:
    account = data.get("account")
    if not isinstance(account, dict):
        account = {}
    return LigmaStatus(
        id=str(data.get("id") or ""),
        content=html_to_plain_text(str(data.get("content") or "")),
        created_at=str(data.get("created_at") or ""),
        display_name=clean_account_text(first_text(account, "display_name", "displayName", "name") or ""),
        username=clean_account_text(first_text(account, "acct", "username") or ""),
        avatar_url=first_text(account, "avatar_static", "avatar", "profile_image_url") or "",
        replies_count=first_int(data, "replies_count", "replies") or 0,
        reblogs_count=first_int(data, "reblogs_count", "reblogs_count", "reblogs") or 0,
        favourites_count=first_int(data, "favourites_count", "favorites_count", "likes") or 0,
        raw=data,
    )


def render_ligma_status(
    status: LigmaStatus,
    avatar_renderer: Callable[[str], list[str]] | None = None,
) -> list[str]:
    header = " ".join(
        item
        for item in (
            status.display_name or "(unknown)",
            f"@{status.username}" if status.username else "",
            format_ligma_date(status.created_at),
        )
        if item
    )
    text_lines = [header]
    content = status.content or f"{LIGMA_BASE_URL}/@{status.username}/{status.id}"
    for paragraph in content.splitlines():
        if not paragraph:
            text_lines.append("")
            continue
        text_lines.extend(
            textwrap.wrap(
                paragraph,
                width=62,
                replace_whitespace=False,
                break_long_words=False,
                break_on_hyphens=False,
            )
            or [""]
        )
    text_lines.append(render_ligma_stats(status))

    avatar_lines = render_avatar_lines(status.avatar_url, avatar_renderer)
    if not avatar_lines:
        return text_lines
    return merge_avatar_and_text(avatar_lines, text_lines)


def render_ligma_stats(status: LigmaStatus) -> str:
    return f"💬 {status.replies_count} ♻️ {status.reblogs_count} ❤️ {status.favourites_count}"


def html_to_plain_text(value: str) -> str:
    parser = LigmaHTMLParser()
    parser.feed(value)
    parser.close()
    text = html.unescape(parser.text())
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()).strip()


class LigmaHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.href_stack: list[str | None] = []
        self.text_stack: list[list[str]] = []

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
            self.text_stack.append([])

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag == "a":
            href = self.href_stack.pop() if self.href_stack else None
            text_parts = self.text_stack.pop() if self.text_stack else []
            link_text = "".join(text_parts).strip()
            if href and should_append_link(href, link_text):
                self.parts.append(f" ({href})")
        if tag == "p":
            self._newline()

    def handle_data(self, data: str):
        self.parts.append(data)
        if self.text_stack:
            self.text_stack[-1].append(data)

    def text(self) -> str:
        return "".join(self.parts)

    def _newline(self) -> None:
        if self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")


def should_append_link(href: str, link_text: str) -> bool:
    if not href.startswith("http"):
        return False
    if "ligma.pro/@" in href:
        return False
    if link_text and link_text in href:
        return False
    return True


def clean_account_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value))).strip()


def format_ligma_date(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%a %b %d %H:%M:%S %z %Y"):
        try:
            parsed = datetime.strptime(value, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.strftime("%b %d %Y")
        except ValueError:
            pass
    return value


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


def indent_lines(lines: list[str], prefix: str) -> list[str]:
    return [prefix + line if line else line for line in lines]


def entrypoint(args, channel, nickname, username, hostname):
    del channel, nickname, username, hostname
    text = " ".join(str(arg) for arg in args).strip()
    if text.isdigit():
        text = f"{LIGMA_BASE_URL}/@r000t/{text}"
    for line in render_ligma_command(text):
        print(line)
