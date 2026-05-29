from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser

from .formatting import italic_title
from .llm import OpenRouterClient, stats_line


URL_CANDIDATE_RE = re.compile(
    r"(?P<url>https?://[^\s<>]+|(?:www\.)?[A-Za-z0-9][A-Za-z0-9.-]*\.[A-Za-z]{2,}[^\s<>]*)"
)
YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
MAX_SOURCE_CHARS = 14_000


class SummaryError(ValueError):
    pass


@dataclass(frozen=True)
class SummaryRequest:
    url: str
    instruction: str
    command: str


@dataclass(frozen=True)
class SummarySource:
    url: str
    kind: str
    title: str | None
    text: str

    @property
    def title_line(self) -> str | None:
        if not self.title:
            return None
        return f"━━☛ {italic_title(self.title[:180])}"


class ReadableHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.in_title = False
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs):
        lowered = tag.lower()
        if lowered == "title":
            self.in_title = True
        if lowered in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1

    def handle_endtag(self, tag: str):
        lowered = tag.lower()
        if lowered == "title":
            self.in_title = False
        if lowered in {"script", "style", "noscript", "svg"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str):
        if self.in_title:
            self.title_parts.append(data)
        if self.skip_depth:
            return
        cleaned = re.sub(r"\s+", " ", data).strip()
        if cleaned:
            self.text_parts.append(cleaned)

    @property
    def title(self) -> str | None:
        title = html.unescape(" ".join(self.title_parts))
        title = re.sub(r"\s+", " ", title).strip()
        return title or None

    @property
    def text(self) -> str:
        text = html.unescape("\n".join(self.text_parts))
        return re.sub(r"\n{3,}", "\n\n", text).strip()


def is_summary_command(text: str) -> bool:
    body = text.strip()
    if not body.startswith("!"):
        return False
    command = body[1:].lstrip().split(maxsplit=1)[0].lower() if body[1:].strip() else ""
    return command in {"summary", "wsummary"}


def parse_summary_command(text: str, fallback_url: str | None = None) -> SummaryRequest:
    body = text.strip()
    if not body.startswith("!"):
        raise SummaryError("Usage: !summary [url] [request]")
    body = body[1:].lstrip()
    if not body:
        raise SummaryError("Usage: !summary [url] [request]")
    parts = body.split(maxsplit=1)
    command = parts[0].lower()
    if command not in {"summary", "wsummary"}:
        raise SummaryError("Usage: !summary [url] [request]")
    rest = parts[1].strip() if len(parts) == 2 else ""
    if rest.lower().startswith("of "):
        rest = rest[3:].lstrip()

    url: str | None = None
    instruction = rest
    match = URL_CANDIDATE_RE.search(rest)
    if match:
        url = _normalize_url(match.group("url").rstrip(").,]"))
        instruction = (rest[: match.start()] + rest[match.end() :]).strip()
    elif rest:
        first, _, remaining = rest.partition(" ")
        if YOUTUBE_ID_RE.match(first):
            url = f"https://youtu.be/{first}"
            instruction = remaining.strip()
    if url is None:
        url = fallback_url
    if url is None:
        raise SummaryError("No URL supplied and no recent URL is known.")
    return SummaryRequest(url=url, instruction=instruction, command=command)


def run_summary_command(
    text: str,
    fallback_url: str | None,
    llm_client: OpenRouterClient,
    model: str,
) -> list[str]:
    request = parse_summary_command(text, fallback_url)
    source = fetch_summary_source(request.url)
    prompt = build_summary_prompt(source, request.instruction)
    result = llm_client.chat(prompt, model)
    lines: list[str] = []
    if source.title_line:
        lines.append(source.title_line)
    lines.extend(result.lines)
    lines.append(stats_line(result))
    return lines


def fetch_summary_source(url: str) -> SummarySource:
    video_id = youtube_video_id(url)
    if video_id:
        return fetch_youtube_transcript(url, video_id)
    return fetch_web_text(url)


def build_summary_prompt(source: SummarySource, instruction: str) -> str:
    request = instruction or (
        "Summarize this source for IRC in concise paragraphs or bullets. "
        "Prioritize concrete claims, context, and the main takeaway."
    )
    return (
        f"{request}\n\n"
        f"Source URL: {source.url}\n"
        f"Source type: {source.kind}\n"
        f"Title: {source.title or '(unknown)'}\n\n"
        f"Content:\n{source.text[:MAX_SOURCE_CHARS]}"
    )


def fetch_web_text(url: str) -> SummarySource:
    request = urllib.request.Request(url, headers={"User-Agent": "pyylmao/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            content_type = response.headers.get("content-type", "").lower()
            raw = response.read(2_000_000)
    except OSError as exc:
        raise SummaryError(f"Could not fetch URL: {exc}") from exc

    if "pdf" in content_type or url.lower().split("?", 1)[0].endswith(".pdf"):
        return _extract_pdf(url, raw)
    decoded = raw.decode(_charset(content_type), errors="replace")
    if "html" in content_type or "<html" in decoded[:500].lower():
        parser = ReadableHTMLParser()
        parser.feed(decoded)
        if not parser.text:
            raise SummaryError("No text extracted from the content.")
        return SummarySource(url=url, kind="webpage", title=parser.title, text=parser.text)
    text = re.sub(r"\s+", " ", decoded).strip()
    if not text:
        raise SummaryError("No text extracted from the content.")
    return SummarySource(url=url, kind="text", title=None, text=text)


def fetch_youtube_transcript(url: str, video_id: str) -> SummarySource:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ModuleNotFoundError as exc:
        raise SummaryError(
            "youtube-transcript-api is required for YouTube summaries. "
            "Install with: python3 -m pip install youtube-transcript-api"
        ) from exc

    try:
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
        else:
            transcript = YouTubeTranscriptApi().fetch(video_id)
    except Exception as exc:
        raise SummaryError(f"Failed to retrieve transcript for video ID '{video_id}': {exc}") from exc

    lines = [_transcript_text(item) for item in transcript]
    text = " ".join(item for item in lines if item).strip()
    if not text:
        raise SummaryError("No transcript text extracted.")
    return SummarySource(
        url=url,
        kind="youtube transcript",
        title=youtube_title(url),
        text=text,
    )


def youtube_video_id(url: str) -> str | None:
    if YOUTUBE_ID_RE.match(url):
        return url
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host == "youtu.be":
        candidate = parsed.path.strip("/").split("/", 1)[0]
        return candidate if YOUTUBE_ID_RE.match(candidate) else None
    if host in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
        query_id = urllib.parse.parse_qs(parsed.query).get("v", [""])[0]
        if YOUTUBE_ID_RE.match(query_id):
            return query_id
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live"} and YOUTUBE_ID_RE.match(parts[1]):
            return parts[1]
    return None


def youtube_title(url: str) -> str | None:
    oembed = "https://www.youtube.com/oembed?" + urllib.parse.urlencode(
        {"url": url, "format": "json"}
    )
    request = urllib.request.Request(oembed, headers={"User-Agent": "pyylmao/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception:
        return None
    title = str(data.get("title") or "").strip()
    author = str(data.get("author_name") or "").strip()
    if title and author:
        return f"{title} | {author}"
    return title or None


def _extract_pdf(url: str, raw: bytes) -> SummarySource:
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:
        raise SummaryError(
            "pypdf is required for PDF summaries. Install with: python3 -m pip install pypdf"
        ) from exc

    try:
        from io import BytesIO

        reader = PdfReader(BytesIO(raw))
        text = "\n".join(page.extract_text() or "" for page in reader.pages[:20]).strip()
    except Exception as exc:
        raise SummaryError(f"Error extracting text from PDF: {exc}") from exc
    if not text:
        raise SummaryError("No text extracted from the content.")
    return SummarySource(url=url, kind="pdf", title=None, text=text)


def _normalize_url(value: str) -> str:
    if value.startswith(("http://", "https://")):
        return value
    return "https://" + value


def _charset(content_type: str) -> str:
    match = re.search(r"charset=([^;]+)", content_type)
    return match.group(1).strip() if match else "utf-8"


def _transcript_text(item) -> str:
    if isinstance(item, dict):
        return str(item.get("text") or "").replace("\n", " ").strip()
    return str(getattr(item, "text", "")).replace("\n", " ").strip()
