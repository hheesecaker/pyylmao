from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


MAX_LINES = 200
MAX_BYTES = 256 * 1024


def parse_cat_path(text: str) -> str | None:
    match = re.match(r"^!cat\s+(.+)$", text.strip(), flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    path = match.group(1).strip()
    return path or None


def is_cat_command(text: str) -> bool:
    return parse_cat_path(text) is not None


@dataclass
class CatFileStore:
    directories: list[Path] = field(default_factory=list)
    max_lines: int = MAX_LINES
    max_bytes: int = MAX_BYTES

    @classmethod
    def default(cls, directory: Path | None = None) -> "CatFileStore":
        directories = [directory] if directory is not None else [Path("data/cat")]
        return cls(directories=directories)

    def handle(self, text: str) -> list[str] | None:
        path = parse_cat_path(text)
        if path is None:
            return None
        return self.get(path)

    def render(self, text: str) -> list[str]:
        path = parse_cat_path(text)
        if path is None:
            return ["Usage: !cat <file>"]
        return self.get(path)

    def get(self, name: str) -> list[str]:
        if not is_safe_relative_path(name):
            return [f"No such file: {name}"]

        for directory in self.directories:
            candidate = safe_join(directory, name)
            if candidate is None or not candidate.is_file():
                continue
            try:
                return self._read(candidate, name)
            except OSError:
                return [f"No such file: {name}"]

        return [f"No such file: {name}"]

    def _read(self, path: Path, display_name: str) -> list[str]:
        with path.open("rb") as handle:
            payload = handle.read(self.max_bytes + 1)
        truncated_bytes = len(payload) > self.max_bytes
        if truncated_bytes:
            payload = payload[: self.max_bytes]

        content = payload.decode("utf-8", errors="replace")
        lines = content.replace("\r\n", "\n").replace("\r", "\n").splitlines()
        if not lines:
            lines = [""]
        if len(lines) > self.max_lines:
            total = len(lines)
            lines = lines[: self.max_lines]
            lines.append(f"error: output truncated to {self.max_lines} of {total} lines total")
        elif truncated_bytes:
            lines.append(f"error: output truncated to {self.max_bytes} bytes from {display_name}")
        return lines


def safe_join(directory: Path, name: str) -> Path | None:
    try:
        root = directory.resolve()
        candidate = (root / name).resolve()
        candidate.relative_to(root)
    except (OSError, ValueError):
        return None
    return candidate


def is_safe_relative_path(name: str) -> bool:
    path = Path(name)
    return (
        bool(name)
        and not path.is_absolute()
        and "\\" not in name
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


def render_cat_command(text: str, store: CatFileStore | None = None) -> list[str]:
    return (store or CatFileStore.default()).render(text)
