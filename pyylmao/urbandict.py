from __future__ import annotations

import json
import re
import textwrap
import urllib.parse
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from .fortune import monospace


SEPARATOR = "─" * 80
NBSP = "\xa0"
IRC_BOLD = "\x02"


class UrbanDictCommandError(Exception):
    pass


@dataclass(frozen=True)
class UrbanEntry:
    word: str
    definition: str
    example: str = ""
    thumbs_up: int = 0


class UrbanDictProvider(Protocol):
    def define(self, term: str, limit: int = 3) -> list[UrbanEntry]:
        ...


class UrbanDictionaryAPIProvider:
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def define(self, term: str, limit: int = 3) -> list[UrbanEntry]:
        query = urllib.parse.urlencode({"term": term})
        url = f"https://api.urbandictionary.com/v0/define?{query}"
        request = urllib.request.Request(url, headers={"User-Agent": "pyylmao/0.1"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))

        entries: list[UrbanEntry] = []
        for item in payload.get("list") or []:
            word = str(item.get("word") or term).strip() or term
            definition = str(item.get("definition") or "").strip()
            if not definition:
                continue
            example = str(item.get("example") or "").strip()
            try:
                thumbs_up = int(item.get("thumbs_up") or 0)
            except (TypeError, ValueError):
                thumbs_up = 0
            entries.append(
                UrbanEntry(
                    word=word,
                    definition=definition,
                    example=example,
                    thumbs_up=thumbs_up,
                )
            )
        entries.sort(key=lambda entry: entry.thumbs_up, reverse=True)
        return entries[:limit]


def is_urban_command(text: str) -> bool:
    return parse_urban_term(text) is not None


def parse_urban_term(text: str) -> str | None:
    match = re.match(r"^!(?:ud|urban)\s+(.+)$", text.strip(), flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    term = match.group(1).strip()
    return term or None


def render_urban_command(
    text: str,
    provider: UrbanDictProvider | None = None,
    limit: int = 3,
) -> list[str]:
    term = parse_urban_term(text)
    if term is None:
        return ["Usage: !urban <term>"]
    provider = provider or UrbanDictionaryAPIProvider()
    try:
        entries = provider.define(term, limit)
    except UrbanDictCommandError:
        raise
    except Exception as exc:
        raise UrbanDictCommandError(f"Urban Dictionary error: {exc}") from exc
    if not entries:
        return [f"No entries found for '{term}'"]

    title_word = entries[0].word or term
    lines = [f"Definitions for {monospace(title_word)}", SEPARATOR]
    for index, entry in enumerate(entries):
        if index:
            lines.append(NBSP)
        lines.extend(wrap_plain(clean_urban_text(entry.definition)))
        if entry.example.strip():
            lines.append(NBSP)
            lines.extend(wrap_example(clean_urban_text(entry.example)))
    lines.append("")
    return lines


def clean_urban_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\[([^\[\]]+)\]", lambda match: f"{IRC_BOLD}{match.group(1)}{IRC_BOLD}", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def wrap_plain(text: str, width: int = 76) -> list[str]:
    return wrap_paragraphs(text, width=width, prefix="")


def wrap_example(text: str, width: int = 74) -> list[str]:
    return wrap_paragraphs(text, width=width, prefix="┃ ")


def wrap_paragraphs(text: str, width: int, prefix: str) -> list[str]:
    lines: list[str] = []
    paragraphs = [part.strip() for part in text.split("\n\n")]
    for paragraph_index, paragraph in enumerate(paragraphs):
        if paragraph_index:
            lines.append(NBSP if not prefix else prefix + NBSP)
        wrapped = wrap_lines(paragraph.splitlines(), width=width)
        if not wrapped:
            lines.append(prefix.rstrip())
            continue
        lines.extend(prefix + line for line in wrapped)
    return lines


def wrap_lines(source_lines: Iterable[str], width: int) -> list[str]:
    out: list[str] = []
    for source_line in source_lines:
        source_line = re.sub(r"\s+", " ", source_line.strip())
        if not source_line:
            out.append("")
            continue
        out.extend(textwrap.wrap(source_line, width=width) or [""])
    return out
