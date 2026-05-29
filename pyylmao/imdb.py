from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


SUGGESTION_BASE_URL = "https://v3.sg.media-imdb.com/suggestion"
CINEMETA_BASE_URL = "https://v3-cinemeta.strem.io/meta"


@dataclass(frozen=True)
class ImdbRequest:
    query: str


@dataclass(frozen=True)
class ImdbTitle:
    imdb_id: str
    title: str
    year: str
    runtime: str
    genres: tuple[str, ...]
    plot: str
    directors: tuple[str, ...]
    writers: tuple[str, ...]
    cast: tuple[str, ...]
    imdb_rating: str
    box_office: str = ""


class ImdbProvider(Protocol):
    def lookup(self, query: str) -> ImdbTitle:
        ...


class ImdbCommandError(RuntimeError):
    pass


class ImdbOnlineProvider:
    def lookup(self, query: str) -> ImdbTitle:
        imdb_id, title_type = self._find_title(query)
        meta = self._fetch_meta(imdb_id, title_type)
        return title_from_meta(imdb_id, meta)

    def _find_title(self, query: str) -> tuple[str, str]:
        normalized = re.sub(r"\s+", "_", query.strip().lower())
        normalized = re.sub(r"[^a-z0-9_]+", "", normalized)
        if not normalized:
            raise ImdbCommandError("Usage: !imdb <title>")
        url = f"{SUGGESTION_BASE_URL}/{normalized[0]}/{quote(normalized)}.json"
        payload = fetch_json(url)
        for item in payload.get("d", []):
            imdb_id = item.get("id", "")
            if not imdb_id.startswith("tt"):
                continue
            title_type = "series" if item.get("qid") in {"tvSeries", "tvMiniSeries"} else "movie"
            return imdb_id, title_type
        raise ImdbCommandError(f"no imdb results for {query!r}")

    def _fetch_meta(self, imdb_id: str, title_type: str) -> dict[str, object]:
        for kind in (title_type, "movie", "series"):
            payload = fetch_json(f"{CINEMETA_BASE_URL}/{kind}/{imdb_id}.json")
            meta = payload.get("meta")
            if isinstance(meta, dict) and meta:
                return meta
        raise ImdbCommandError(f"no imdb metadata for {imdb_id}")


DEFAULT_PROVIDER = ImdbOnlineProvider()


def is_imdb_command(text: str) -> bool:
    return parse_imdb_command(text) is not None


def parse_imdb_command(text: str) -> ImdbRequest | None:
    match = re.match(r"^!imdb(?:\d{1,2})?(?:24)?\s+(.+)$", text.strip(), flags=re.IGNORECASE)
    if not match:
        return None
    query = match.group(1).strip()
    if not query:
        return None
    return ImdbRequest(query=query)


def render_imdb_command(text: str, provider: ImdbProvider | None = None) -> list[str]:
    request = parse_imdb_command(text)
    if request is None:
        return ["Usage: !imdb <title>"]
    try:
        title = (provider or DEFAULT_PROVIDER).lookup(request.query)
    except (ImdbCommandError, HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise ImdbCommandError(str(exc)) from exc
    return render_title(title)


def render_title(title: ImdbTitle) -> list[str]:
    lines = [f"{title.title} ({title.year}) https://www.imdb.com/title/{title.imdb_id}/"]
    lines.append(f"Runtime: {title.runtime or 'N/A'}")
    lines.append(f"Genre: {join_or_na(title.genres)}")
    if title.plot:
        lines.extend(wrap_prefixed("Plot: ", title.plot, width=390))
    lines.append(f"Director: {join_or_na(title.directors)}")
    lines.append(f"Writer: {join_or_na(title.writers)}")
    lines.append(f"Starring: {join_or_na(title.cast)}")
    lines.append("Ratings:")
    if title.imdb_rating and title.imdb_rating != "N/A":
        lines.append(f"Internet Movie Database: {stars_for_rating(title.imdb_rating)} ({title.imdb_rating}/10)")
    else:
        lines.append("Internet Movie Database: N/A")
    if title.box_office:
        lines.append(f"Box Office: {title.box_office}")
    return lines


def title_from_meta(imdb_id: str, meta: dict[str, object]) -> ImdbTitle:
    return ImdbTitle(
        imdb_id=str(meta.get("imdb_id") or imdb_id),
        title=str(meta.get("name") or "N/A"),
        year=str(meta.get("year") or meta.get("releaseInfo") or "N/A"),
        runtime=str(meta.get("runtime") or "N/A"),
        genres=string_tuple(meta.get("genre") or meta.get("genres")),
        plot=str(meta.get("description") or ""),
        directors=string_tuple(meta.get("director")),
        writers=string_tuple(meta.get("writer")),
        cast=string_tuple(meta.get("cast"))[:3],
        imdb_rating=str(meta.get("imdbRating") or "N/A"),
        box_office=str(meta.get("boxOffice") or ""),
    )


def string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, list):
        return tuple(str(item) for item in value if str(item))
    return ()


def join_or_na(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "N/A"


def stars_for_rating(rating: str) -> str:
    try:
        rounded = max(0, min(10, round(float(rating))))
    except ValueError:
        return "N/A"
    return " ".join(["★"] * rounded + ["☆"] * (10 - rounded))


def wrap_prefixed(prefix: str, text: str, width: int) -> list[str]:
    words = text.split()
    if not words:
        return [prefix.rstrip()]
    lines: list[str] = []
    current = prefix
    continuation = " " * len(prefix)
    for word in words:
        separator = "" if current.endswith(" ") else " "
        if len(current) + len(separator) + len(word) > width and current.strip():
            lines.append(current.rstrip())
            current = continuation + word
        else:
            current += separator + word
    lines.append(current.rstrip())
    return lines


def fetch_json(url: str) -> dict[str, object]:
    request = Request(url, headers={"User-Agent": "pyylmao"})
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))
