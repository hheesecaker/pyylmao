from __future__ import annotations

import json
import re
import textwrap
import urllib.parse
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol


BOLD_TRANS = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
    "𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗",
)


class DefineCommandError(Exception):
    pass


@dataclass(frozen=True)
class Definition:
    text: str
    example: str = ""


@dataclass(frozen=True)
class Meaning:
    part_of_speech: str
    definitions: list[Definition]


@dataclass(frozen=True)
class DictionaryEntry:
    word: str
    phonetic: str
    meanings: list[Meaning]


class DefineProvider(Protocol):
    def lookup(self, word: str) -> list[DictionaryEntry]:
        ...


class DictionaryAPIProvider:
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def lookup(self, word: str) -> list[DictionaryEntry]:
        url_word = urllib.parse.quote(word)
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{url_word}"
        request = urllib.request.Request(url, headers={"User-Agent": "pyylmao/0.1"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, list):
            return []
        return [entry for item in payload if (entry := parse_dictionary_entry(item)) is not None]


def parse_dictionary_entry(item: object) -> DictionaryEntry | None:
    if not isinstance(item, dict):
        return None
    word = str(item.get("word") or "").strip()
    if not word:
        return None
    phonetic = str(item.get("phonetic") or "").strip()
    if not phonetic:
        for phonetic_item in item.get("phonetics") or []:
            if isinstance(phonetic_item, dict) and str(phonetic_item.get("text") or "").strip():
                phonetic = str(phonetic_item["text"]).strip()
                break

    meanings: list[Meaning] = []
    for meaning_item in item.get("meanings") or []:
        if not isinstance(meaning_item, dict):
            continue
        part_of_speech = str(meaning_item.get("partOfSpeech") or "").strip()
        definitions: list[Definition] = []
        for definition_item in meaning_item.get("definitions") or []:
            if not isinstance(definition_item, dict):
                continue
            definition = str(definition_item.get("definition") or "").strip()
            if not definition:
                continue
            example = str(definition_item.get("example") or "").strip()
            definitions.append(Definition(definition, example))
        if part_of_speech and definitions:
            meanings.append(Meaning(part_of_speech, definitions))

    if not meanings:
        return None
    return DictionaryEntry(word=word, phonetic=phonetic, meanings=meanings)


def is_define_command(text: str) -> bool:
    return parse_define_word(text) is not None


def parse_define_word(text: str) -> str | None:
    match = re.match(r"^!define\s+(.+)$", text.strip(), flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    word = match.group(1).strip()
    return word or None


def render_define_command(
    text: str,
    provider: DefineProvider | None = None,
    definitions_per_part: int = 4,
) -> list[str]:
    word = parse_define_word(text)
    if word is None:
        return ["Usage: !define <word>"]
    provider = provider or DictionaryAPIProvider()
    try:
        entries = provider.lookup(word)
    except DefineCommandError:
        raise
    except Exception as exc:
        raise DefineCommandError(f"define error: {exc}") from exc
    if not entries:
        return [f"No definitions found for '{word}'"]
    return render_dictionary_entry(entries[0], definitions_per_part=definitions_per_part)


def render_dictionary_entry(entry: DictionaryEntry, definitions_per_part: int = 4) -> list[str]:
    header = entry.word
    if entry.phonetic:
        header = f"{header} {entry.phonetic}"

    lines = [header, ""]
    for meaning in entry.meanings:
        lines.extend([bold_text(meaning.part_of_speech.title()), "", ""])
        for definition in meaning.definitions[:definitions_per_part]:
            lines.extend(wrap_prefixed(definition.text, first_prefix="  • ", rest_prefix="    "))
            if definition.example:
                lines.extend(
                    wrap_prefixed(
                        f"Example: {definition.example}",
                        first_prefix="    ",
                        rest_prefix="    ",
                    )
                )
            lines.append("")
        lines.append("")
    return lines


def wrap_prefixed(text: str, first_prefix: str, rest_prefix: str, width: int = 390) -> list[str]:
    clean = re.sub(r"\s+", " ", text.strip())
    if not clean:
        return [first_prefix.rstrip()]
    available = max(20, width - len(first_prefix))
    wrapped = textwrap.wrap(clean, width=available) or [clean]
    lines = [first_prefix + wrapped[0]]
    continuation_width = max(20, width - len(rest_prefix))
    for fragment in rewrap_fragments(wrapped[1:], continuation_width):
        lines.append(rest_prefix + fragment)
    return lines


def rewrap_fragments(fragments: Iterable[str], width: int) -> list[str]:
    text = " ".join(fragment.strip() for fragment in fragments if fragment.strip())
    if not text:
        return []
    return textwrap.wrap(text, width=width) or [text]


def bold_text(text: str) -> str:
    return text.translate(BOLD_TRANS)
