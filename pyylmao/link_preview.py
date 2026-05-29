from __future__ import annotations

import html
import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

from .formatting import italic_title
from .summary import youtube_video_id


URL_RE = re.compile(r"https?://[^\s<>]+")
IRC_BOLD = "\x02"
IRC_COLOR = "\x03"
IRC_RESET = "\x0f"


class TitleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        if tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag: str):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str):
        if self.in_title:
            self.parts.append(data)

    @property
    def title(self) -> str:
        return html.unescape(" ".join(self.parts).strip())


def first_url(text: str) -> str | None:
    match = URL_RE.search(text)
    if not match:
        return None
    return match.group(0).rstrip(").,]")


@dataclass(frozen=True)
class YouTubePreview:
    title: str
    author: str | None = None
    duration_seconds: int | None = None
    view_count: int | None = None
    like_count: int | None = None
    live_status: str | None = None
    upload_date: str | None = None


def is_youtube_url(url: str) -> bool:
    return youtube_video_id(url) is not None


def preview_title(url: str, timeout: float = 8.0) -> str:
    if is_youtube_url(url):
        return preview_youtube(url, timeout)
    request = urllib.request.Request(url, headers={"User-Agent": "pyylmao/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type and "text" not in content_type:
            raise ValueError(f"not an HTML page: {content_type}")
        raw = response.read(256_000).decode("utf-8", errors="replace")
    parser = TitleParser()
    parser.feed(raw)
    title = parser.title
    if not title:
        raise ValueError("no title found")
    return f"━━☛ {italic_title(title[:180])}"


def preview_youtube(url: str, timeout: float = 8.0) -> str:
    metadata = fetch_youtube_preview(url, timeout)
    return render_youtube_preview(metadata)


def fetch_youtube_preview(url: str, timeout: float = 8.0) -> YouTubePreview:
    metadata = fetch_youtube_with_ytdlp(url)
    metadata = merge_youtube_preview(metadata, fetch_youtube_innertube(url, timeout))
    metadata = merge_youtube_preview(metadata, fetch_youtube_web_metadata(url, timeout))
    try:
        metadata = merge_youtube_preview(metadata, fetch_youtube_oembed(url, timeout))
    except Exception:
        if metadata is None:
            raise
    if metadata is None:
        raise ValueError("no YouTube title found")
    return metadata


def fetch_youtube_with_ytdlp(url: str) -> YouTubePreview | None:
    try:
        from yt_dlp import YoutubeDL
    except ModuleNotFoundError:
        return None

    options = {
        "extract_flat": False,
        "noplaylist": True,
        "quiet": True,
        "skip_download": True,
        "socket_timeout": 12,
        "no_warnings": True,
        "logger": QuietYtdlpLogger(),
    }
    cookie_file = os.getenv("PYYLMAO_YOUTUBE_COOKIES")
    if cookie_file:
        options["cookiefile"] = cookie_file
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return None
    if not isinstance(info, dict):
        return None
    title = _clean_youtube_text(info.get("title"))
    if not title:
        return None
    return YouTubePreview(
        title=title,
        author=_clean_youtube_text(
            info.get("channel") or info.get("uploader") or info.get("creator")
        ),
        duration_seconds=_int_or_none(info.get("duration")),
        view_count=_int_or_none(info.get("view_count")),
        like_count=_int_or_none(info.get("like_count")),
        live_status=_clean_youtube_text(info.get("live_status")),
        upload_date=format_youtube_date(
            info.get("upload_date")
            or info.get("release_date")
            or info.get("timestamp")
            or info.get("release_timestamp")
        ),
    )


def fetch_youtube_innertube(url: str, timeout: float = 8.0) -> YouTubePreview | None:
    video_id = youtube_video_id(url)
    if video_id is None:
        return None
    payload = {
        "context": {
            "client": {
                "clientName": "WEB",
                "clientVersion": "2.20260527.01.00",
            }
        },
        "videoId": video_id,
        "contentCheckOk": True,
        "racyCheckOk": True,
    }
    request = urllib.request.Request(
        "https://www.youtube.com/youtubei/v1/player?prettyPrint=false",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read(500_000).decode("utf-8", errors="replace"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    metadata = youtube_player_response_preview(data)
    if metadata is None:
        return None
    return enrich_youtube_oembed_preview(url, metadata, timeout)


def fetch_youtube_oembed(url: str, timeout: float = 8.0) -> YouTubePreview:
    oembed = "https://www.youtube.com/oembed?" + urllib.parse.urlencode(
        {"url": url, "format": "json"}
    )
    request = urllib.request.Request(oembed, headers={"User-Agent": "pyylmao/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8", errors="replace"))
    title = _clean_youtube_text(data.get("title"))
    if not title:
        raise ValueError("no YouTube title found")
    preview = YouTubePreview(
        title=title,
        author=_clean_youtube_text(data.get("author_name")),
    )
    return enrich_youtube_oembed_preview(url, preview, timeout)


def fetch_youtube_web_metadata(url: str, timeout: float = 8.0) -> YouTubePreview | None:
    video_id = youtube_video_id(url)
    if video_id is None:
        return None
    urls = [url]
    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    shorts_url = f"https://www.youtube.com/shorts/{video_id}"
    for candidate in (watch_url, shorts_url):
        if candidate not in urls:
            urls.append(candidate)
    for candidate in urls:
        request = urllib.request.Request(
            candidate,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                text = response.read(1_500_000).decode("utf-8", errors="replace")
        except Exception:
            continue
        metadata = parse_youtube_initial_data(text)
        if metadata is not None:
            return metadata
    return None


def render_youtube_preview(metadata: YouTubePreview) -> str:
    title = _clean_youtube_text(metadata.title) or "(untitled)"
    line = f"{youtube_logo()} {IRC_COLOR}1,15 {title}"
    author = _clean_youtube_text(metadata.author)
    if author:
        line += f" | {author}"
    line += f" {IRC_RESET}"

    status = youtube_status_label(metadata)
    views = compact_count(metadata.view_count)
    likes = compact_count(metadata.like_count)
    islands = []
    if status is not None:
        islands.append(youtube_status_island(f"[{status}]"))
    if views is not None:
        islands.append(youtube_count_island(views, "views", IRC_COLOR))
    if likes is not None:
        islands.append(youtube_count_island(likes, "likes", IRC_RESET))
    upload_date = format_youtube_date(metadata.upload_date)
    if upload_date is not None:
        islands.append(youtube_date_island(upload_date))
    for island in islands:
        line += " " + island
    return line


def youtube_logo() -> str:
    return f"{IRC_COLOR}0,4 ▶ {IRC_RESET}"


def youtube_status_island(text: str) -> str:
    value = _clean_youtube_text(text) or ""
    return f"{IRC_COLOR}1,15{value}{IRC_RESET}"


def youtube_count_island(count: str, unit: str, reset: str) -> str:
    value = _clean_youtube_text(count) or "0"
    unit = _clean_youtube_text(unit) or ""
    return f"{IRC_COLOR}1,15 {IRC_BOLD}{value}{IRC_BOLD} {unit} {reset}"


def youtube_date_island(text: str) -> str:
    value = _clean_youtube_text(text) or ""
    return f"{IRC_COLOR}1,15 {IRC_BOLD}{value}{IRC_BOLD}{IRC_RESET}"


def merge_youtube_preview(
    base: YouTubePreview | None, extra: YouTubePreview | None
) -> YouTubePreview | None:
    if base is None:
        return extra
    if extra is None:
        return base
    return YouTubePreview(
        title=base.title or extra.title,
        author=base.author or extra.author,
        duration_seconds=(
            base.duration_seconds
            if base.duration_seconds is not None
            else extra.duration_seconds
        ),
        view_count=base.view_count if base.view_count is not None else extra.view_count,
        like_count=base.like_count if base.like_count is not None else extra.like_count,
        live_status=base.live_status or extra.live_status,
        upload_date=base.upload_date or extra.upload_date,
    )


def youtube_status_label(metadata: YouTubePreview) -> str | None:
    live_status = (metadata.live_status or "").lower().replace("-", "_")
    if live_status in {"is_live", "live"}:
        return "LIVE"
    if live_status in {"is_upcoming", "upcoming"}:
        return "UPCOMING"
    if metadata.duration_seconds is not None:
        return format_duration(metadata.duration_seconds)
    return None


def format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def compact_count(value: int | None) -> str | None:
    if value is None:
        return None
    count = max(0, int(value))
    if count < 1_000:
        return str(count)
    if count < 1_000_000:
        return f"{round(count / 1_000):.0f}K"
    return f"{count / 1_000_000:.1f}M"


def format_youtube_date(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), timezone.utc).strftime("%b %d, %Y")
        except (OSError, OverflowError, ValueError):
            return None
    text = _clean_youtube_text(value)
    if not text:
        return None
    if re.fullmatch(r"\d{8}", text):
        try:
            return datetime.strptime(text, "%Y%m%d").strftime("%b %d, %Y")
        except ValueError:
            return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            normalized = text.replace("Z", "+0000")
            parsed = datetime.strptime(normalized, fmt)
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(timezone.utc)
            return parsed.strftime("%b %d, %Y")
        except ValueError:
            continue
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%b %d, %Y")
        except ValueError:
            continue
    relative = relative_youtube_date(text)
    if relative is not None:
        return relative
    return None


def relative_youtube_date(text: str, now: datetime | None = None) -> str | None:
    normalized = text.lower().strip()
    if normalized in {"yesterday", "premiered yesterday", "streamed yesterday"}:
        base = now or datetime.now(timezone.utc)
        return (base - timedelta(days=1)).strftime("%b %d, %Y")
    match = re.search(
        r"(?:premiered|streamed|started)?\s*(\d+)\s+"
        r"(second|minute|hour|day|week|month|year)s?\s+ago",
        normalized,
    )
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2)
    days_per_unit = {
        "second": 0,
        "minute": 0,
        "hour": 0,
        "day": 1,
        "week": 7,
        "month": 30,
        "year": 365,
    }
    if unit in {"second", "minute", "hour"}:
        delta = timedelta(**{unit + "s": amount})
    else:
        delta = timedelta(days=days_per_unit[unit] * amount)
    base = now or datetime.now(timezone.utc)
    return (base - delta).strftime("%b %d, %Y")


def parse_youtube_initial_data(text: str) -> YouTubePreview | None:
    data = extract_youtube_initial_data(text)
    if data is not None:
        header = find_video_description_header(data)
        if header is not None:
            title = youtube_text(header.get("title"))
            if title:
                return YouTubePreview(
                    title=title,
                    author=youtube_text(header.get("channel")),
                    view_count=parse_youtube_count(youtube_text(header.get("views"))),
                    like_count=header_like_count(header),
                    upload_date=format_youtube_date(
                        youtube_text(header.get("publishDate")) or header_factoid_date(header)
                    ),
                )
    player = extract_youtube_initial_player_response(text)
    if player is not None:
        metadata = youtube_player_response_preview(player)
        if metadata is not None:
            return metadata
    return youtube_html_metadata_preview(text)


def extract_youtube_initial_data(text: str):
    for marker in ("var ytInitialData = ", "ytInitialData = "):
        index = text.find(marker)
        if index < 0:
            continue
        start = text.find("{", index)
        if start < 0:
            continue
        try:
            return json.JSONDecoder().raw_decode(text[start:])[0]
        except json.JSONDecodeError:
            continue
    return None


def extract_youtube_initial_player_response(text: str):
    for marker in ("var ytInitialPlayerResponse = ", "ytInitialPlayerResponse = "):
        index = text.find(marker)
        if index < 0:
            continue
        start = text.find("{", index)
        if start < 0:
            continue
        try:
            return json.JSONDecoder().raw_decode(text[start:])[0]
        except json.JSONDecodeError:
            continue
    return None


def youtube_player_response_preview(data: dict) -> YouTubePreview | None:
    if not isinstance(data, dict):
        return None
    details = data.get("videoDetails") if isinstance(data.get("videoDetails"), dict) else {}
    micro_root = data.get("microformat") if isinstance(data.get("microformat"), dict) else {}
    micro = (
        micro_root.get("playerMicroformatRenderer")
        if isinstance(micro_root.get("playerMicroformatRenderer"), dict)
        else {}
    )
    title = _clean_youtube_text(details.get("title")) or youtube_text(micro.get("title"))
    if not title:
        return None
    return YouTubePreview(
        title=title,
        author=_clean_youtube_text(details.get("author"))
        or youtube_text(micro.get("ownerChannelName")),
        duration_seconds=_int_or_none(details.get("lengthSeconds"))
        or parse_youtube_duration(micro.get("lengthSeconds")),
        view_count=_int_or_none(details.get("viewCount")),
        live_status="is_live" if details.get("isLiveContent") is True else None,
        upload_date=format_youtube_date(
            micro.get("uploadDate")
            or micro.get("publishDate")
            or innertube_live_start(micro.get("liveBroadcastDetails"))
        ),
    )


def youtube_html_metadata_preview(text: str) -> YouTubePreview | None:
    title = (
        html_meta_content(text, "og:title")
        or html_meta_content(text, "twitter:title")
        or html_meta_content(text, "name")
    )
    if title and title.endswith(" - YouTube"):
        title = title[: -len(" - YouTube")].strip()
    author = html_meta_content(text, "author")
    upload_date = format_youtube_date(
        html_meta_content(text, "uploadDate")
        or html_meta_content(text, "datePublished")
        or html_meta_content(text, "og:video:release_date")
        or html_meta_content(text, "article:published_time")
        or regex_youtube_date(text)
    )
    duration = parse_youtube_duration(html_meta_content(text, "duration"))
    views = parse_youtube_count(html_meta_content(text, "interactionCount"))
    if not any((title, author, upload_date, duration, views)):
        return None
    return YouTubePreview(
        title=title or "",
        author=author,
        duration_seconds=duration,
        view_count=views,
        upload_date=upload_date,
    )


def html_meta_content(text: str, *keys: str) -> str | None:
    wanted = {key.lower() for key in keys}
    for match in re.finditer(r"<meta\b[^>]*>", text, re.IGNORECASE):
        attrs = {
            name.lower(): html.unescape(value)
            for name, _, value in re.findall(
                r"([:\w-]+)\s*=\s*(['\"])(.*?)\2", match.group(0), re.DOTALL
            )
        }
        key = (
            attrs.get("property")
            or attrs.get("name")
            or attrs.get("itemprop")
            or ""
        ).lower()
        if key in wanted:
            content = _clean_youtube_text(attrs.get("content"))
            if content:
                return content
    return None


def regex_youtube_date(text: str) -> str | None:
    for pattern in (
        r'"(?:publishDate|uploadDate|datePublished)"\s*:\s*"([^"]+)"',
        r'"dateText"\s*:\s*\{\s*"simpleText"\s*:\s*"([^"]+)"',
    ):
        match = re.search(pattern, text)
        if match:
            return html.unescape(match.group(1))
    return None


def find_video_description_header(value):
    if isinstance(value, dict):
        header = value.get("videoDescriptionHeaderRenderer")
        if isinstance(header, dict):
            return header
        for child in value.values():
            found = find_video_description_header(child)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_video_description_header(child)
            if found is not None:
                return found
    return None


def youtube_text(value) -> str | None:
    if isinstance(value, str):
        return _clean_youtube_text(value)
    if not isinstance(value, dict):
        return None
    simple = _clean_youtube_text(value.get("simpleText"))
    if simple:
        return simple
    runs = value.get("runs")
    if isinstance(runs, list):
        text = "".join(str(run.get("text", "")) for run in runs if isinstance(run, dict))
        return _clean_youtube_text(text)
    return None


def header_like_count(header: dict) -> int | None:
    for renderer in iter_header_factoid_renderers(header):
        label = (youtube_text(renderer.get("label")) or "").lower()
        if label == "likes":
            return parse_youtube_count(
                youtube_text(renderer.get("value"))
                or _clean_youtube_text(renderer.get("accessibilityText"))
            )
    return None


def header_factoid_date(header: dict) -> str | None:
    for renderer in iter_header_factoid_renderers(header):
        accessibility = format_youtube_date(renderer.get("accessibilityText"))
        if accessibility:
            return accessibility
        value = youtube_text(renderer.get("value"))
        label = youtube_text(renderer.get("label"))
        if value and label:
            formatted = format_youtube_date(f"{value}, {label}") or format_youtube_date(
                f"{value} {label}"
            )
            if formatted:
                return formatted
    return None


def iter_header_factoid_renderers(header: dict):
    for item in header.get("factoid") or []:
        if not isinstance(item, dict):
            continue
        renderer = item.get("factoidRenderer")
        if isinstance(renderer, dict):
            yield renderer
        view_count = item.get("viewCountFactoidRenderer")
        if isinstance(view_count, dict):
            factoid = view_count.get("factoid")
            if isinstance(factoid, dict) and isinstance(factoid.get("factoidRenderer"), dict):
                yield factoid["factoidRenderer"]


def parse_youtube_count(text: str | None) -> int | None:
    text = _clean_youtube_text(text)
    if not text:
        return None
    compact = re.search(r"([\d,.]+)\s*([KMB])\b", text, re.IGNORECASE)
    if compact:
        try:
            number = float(compact.group(1).replace(",", ""))
        except ValueError:
            return None
        multiplier = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[
            compact.group(2).lower()
        ]
        return int(number * multiplier)
    digits = re.search(r"[\d,]+", text)
    if not digits:
        return None
    try:
        return int(digits.group(0).replace(",", ""))
    except ValueError:
        return None


def parse_youtube_duration(value) -> int | None:
    if value is None:
        return None
    seconds = _int_or_none(value)
    if seconds is not None:
        return seconds
    text = _clean_youtube_text(value)
    if not text:
        return None
    match = re.fullmatch(
        r"P(?:\d+D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?",
        text,
    )
    if not match:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def innertube_live_start(value) -> str | None:
    if not isinstance(value, dict):
        return None
    return _clean_youtube_text(value.get("startTimestamp"))


def enrich_youtube_oembed_preview(url: str, preview: YouTubePreview, timeout: float) -> YouTubePreview:
    video_id = youtube_video_id(url)
    if video_id is None:
        return preview
    stats = fetch_return_youtube_dislike_stats(video_id, timeout)
    if stats is None:
        return preview
    return YouTubePreview(
        title=preview.title,
        author=preview.author,
        duration_seconds=preview.duration_seconds,
        view_count=preview.view_count if preview.view_count is not None else stats.get("view_count"),
        like_count=preview.like_count if preview.like_count is not None else stats.get("like_count"),
        live_status=preview.live_status,
        upload_date=preview.upload_date,
    )


def fetch_return_youtube_dislike_stats(video_id: str, timeout: float) -> dict[str, int] | None:
    endpoint = "https://returnyoutubedislikeapi.com/votes?" + urllib.parse.urlencode(
        {"videoId": video_id}
    )
    request = urllib.request.Request(
        endpoint,
        headers={"User-Agent": "pyylmao/0.1", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read(20_000).decode("utf-8", errors="replace"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    stats: dict[str, int] = {}
    views = _int_or_none(data.get("viewCount"))
    likes = _int_or_none(data.get("likes"))
    if views is not None:
        stats["view_count"] = views
    if likes is not None:
        stats["like_count"] = likes
    return stats or None


def _int_or_none(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_youtube_text(value) -> str | None:
    if value is None:
        return None
    text = html.unescape(str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


class QuietYtdlpLogger:
    def debug(self, message: str) -> None:
        del message

    def warning(self, message: str) -> None:
        del message

    def error(self, message: str) -> None:
        del message
