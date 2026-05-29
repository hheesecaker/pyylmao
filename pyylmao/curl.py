from __future__ import annotations

import re
import urllib.request
from dataclasses import dataclass
from typing import Protocol


MAX_LINES = 60
MAX_BYTES = 256 * 1024


class CurlCommandError(Exception):
    pass


@dataclass(frozen=True)
class CurlRequest:
    command: str
    url: str
    rest: str = ""


class CurlFetcher(Protocol):
    def fetch(self, url: str, max_bytes: int = MAX_BYTES) -> bytes:
        ...


class URLCurlFetcher:
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def fetch(self, url: str, max_bytes: int = MAX_BYTES) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": "pyylmao/0.1"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return response.read(max_bytes + 1)


def is_curl_command(text: str) -> bool:
    return parse_curl_request(text) is not None


def parse_curl_request(text: str) -> CurlRequest | None:
    match = re.match(r"^!(curl2?|curl)\s+(https?://\S+)(?:\s+(.*))?$", text.strip(), flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    command, url, rest = match.groups()
    return CurlRequest(command=command.lower(), url=url, rest=(rest or "").strip())


def render_curl_command(
    text: str,
    fetcher: CurlFetcher | None = None,
    max_lines: int = MAX_LINES,
    max_bytes: int = MAX_BYTES,
) -> list[str]:
    request = parse_curl_request(text)
    if request is None:
        return ["Usage: !curl <url>"]
    fetcher = fetcher or URLCurlFetcher()
    try:
        payload = fetcher.fetch(request.url, max_bytes=max_bytes)
    except CurlCommandError:
        raise
    except Exception as exc:
        raise CurlCommandError(str(exc)) from exc
    if len(payload) > max_bytes:
        raise CurlCommandError(f"curl output exceeded {max_bytes} bytes")

    try:
        data = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        if request.command == "curl":
            raise CurlCommandError(str(exc)) from exc
        data = payload.decode("utf-8", errors="replace")

    lines = data.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if request.command == "curl2":
        lines = [line for line in lines if line.strip()]
    if not lines:
        lines = [""]
    if len(lines) > max_lines:
        total = len(lines)
        lines = lines[:max_lines]
        lines.append(f"error: output truncated to {max_lines} of {total} lines total")
    return lines
