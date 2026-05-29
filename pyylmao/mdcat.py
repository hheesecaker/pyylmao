from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .cat import is_safe_relative_path, safe_join
from .define import bold_text
from .echo import render_inline_markdown, render_quote_line


MAX_LINES = 200
MAX_BYTES = 256 * 1024
HISTORICAL_TMP_ROOT = "/usr/src/app/assets/tmp"
TABLE_SEP = "🭍"

DEFAULT_MDCAT_OPTIONS: dict[str, Any] = {
    "syntax": {"background_color": "#222222", "padding": "1,1"},
    "use_figlet": "False",
    "table_wrap": True,
    "inline_code_suffix": "\x0f\x0311",
    "inline_code_fg": "10",
    "inline_code_bg": "89",
    "h1_font": "phm-rounded",
}


def parse_mdcat_path(text: str) -> str | None:
    match = re.match(r"^!mdcat\s+(.+)$", text.strip(), flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    path = match.group(1).strip()
    return path or None


def is_mdcat_command(text: str) -> bool:
    return parse_mdcat_path(text) is not None


@dataclass
class MdCatStore:
    directories: list[Path] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_MDCAT_OPTIONS))
    max_lines: int = MAX_LINES
    max_bytes: int = MAX_BYTES
    display_root: str = HISTORICAL_TMP_ROOT

    @classmethod
    def default(cls, directory: Path | None = None) -> "MdCatStore":
        directories = [directory] if directory is not None else [Path("data/mdcat")]
        return cls(directories=directories)

    def render(self, text: str) -> list[str]:
        name = parse_mdcat_path(text)
        if name is None:
            return ["Usage: !mdcat <file>"]

        prelude = [repr(self.options)]
        if not is_safe_relative_path(name):
            return prelude + [self.missing_line(name)]

        for directory in self.directories:
            candidate = safe_join(directory, name)
            if candidate is None or not candidate.is_file():
                continue
            try:
                return prelude + self._read(candidate, name)
            except OSError as exc:
                return prelude + [f"mdcat: error reading file: {exc!r}"]

        return prelude + [self.missing_line(name)]

    def missing_line(self, name: str) -> str:
        return f"mdcat: no such file @ {self.display_root}/{name}"

    def _read(self, path: Path, display_name: str) -> list[str]:
        with path.open("rb") as handle:
            payload = handle.read(self.max_bytes + 1)
        truncated_bytes = len(payload) > self.max_bytes
        if truncated_bytes:
            payload = payload[: self.max_bytes]

        content = payload.decode("utf-8", errors="replace")
        lines = render_markdown_document(content)
        if len(lines) > self.max_lines:
            total = len(lines)
            lines = lines[: self.max_lines]
            lines.append(f"error: output truncated to {self.max_lines} of {total} lines total")
        elif truncated_bytes:
            lines.append(f"error: output truncated to {self.max_bytes} bytes from {display_name}")
        return lines


def render_mdcat_command(text: str, store: MdCatStore | None = None) -> list[str]:
    return (store or MdCatStore.default()).render(text)


def render_markdown_document(text: str) -> list[str]:
    raw_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    index = 0
    while index < len(raw_lines):
        if is_table_start(raw_lines, index):
            table_rows: list[list[str]] = [split_table_row(raw_lines[index])]
            index += 2
            while index < len(raw_lines) and "|" in raw_lines[index].strip():
                table_rows.append(split_table_row(raw_lines[index]))
                index += 1
            out.extend(render_table(table_rows))
            continue

        out.append(render_markdown_line(raw_lines[index]))
        index += 1
    return out or [""]


def render_markdown_line(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ""
    heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
    if heading:
        return bold_text(render_inline_markdown(heading.group(2).strip()))
    if stripped.startswith(">"):
        return render_quote_line(line)
    bullet = re.match(r"^[-*]\s+(.+)$", stripped)
    if bullet:
        return "  • " + render_inline_markdown(bullet.group(1))
    ordered = re.match(r"^(\d+\.)\s*(.*)$", stripped)
    if ordered:
        rest = render_inline_markdown(ordered.group(2)) if ordered.group(2) else ""
        return f"  {ordered.group(1)}" + (f" {rest}" if rest else "")
    return render_inline_markdown(line)


def is_table_start(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    header = lines[index].strip()
    separator = lines[index + 1].strip()
    return "|" in header and bool(re.match(r"^\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?$", separator))


def split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [render_inline_markdown(cell.strip()) for cell in stripped.split("|")]


def render_table(rows: list[list[str]]) -> list[str]:
    if not rows:
        return []
    column_count = max(len(row) for row in rows)
    normalized = [row + [""] * (column_count - len(row)) for row in rows]
    widths = [
        max(4, *(len(row[column]) for row in normalized))
        for column in range(column_count)
    ]
    lines = [" " * min(sum(widths) + 4 * column_count, 100)]
    for row in normalized:
        cells = [row[column].ljust(widths[column]) for column in range(column_count)]
        lines.append(" " + f" {TABLE_SEP}  ".join(cells) + f" {TABLE_SEP}")
    lines.append(" ".join("🮝" + "🮘" * width + "🮟" for width in widths))
    return lines
