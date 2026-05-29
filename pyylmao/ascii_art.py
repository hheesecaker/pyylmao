from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


PCP_BLOCK = "▀" * 72

BUILTIN_ART: dict[str, list[str]] = {
    "pcp": [PCP_BLOCK] * 8,
    "clipboard": [
        "               |         |                                |                 |",
        "               |         |              EQ                |                 |",
        "               |         |   CHANNEL 1       CHANNEL 2    | SNITCH 'O METER |",
        "               |         |                                |                 |",
        "               |         |                                |                 |",
        "               |         |                                |                 |",
        "               |         |                                |                 |",
        "               |         |                                |                 |         ----------------------",
        "               |         |                                |                 |           Virtual Xistential",
        "       R A G E | P A I N |  RA GE  HA TE    RA GE  HA TE  | LEVEL     LIMIT |                 Pussy",
        "        ratio  | control |                                |                 | POWER",
        "               _         _  'This Product  Discontin  d'  _                 _                           spoke",
        "",
    ],
    "vxpussy": [
        "               |         |                                |                 |",
        "               |         |              EQ                |                 |",
        "               |         |   CHANNEL 1       CHANNEL 2    | SNITCH 'O METER |",
        "               |         |                                |                 |",
        "               |         |                                |                 |",
        "               |         |                                |                 |",
        "               |         |                                |                 |",
        "               |         |                                |                 |         ----------------------",
        "               |         |                                |                 |           Virtual Xistential",
        "       R A G E | P A I N |  RA GE  HA TE    RA GE  HA TE  | LEVEL     LIMIT |                 Pussy",
        "        ratio  | control |                                |                 | POWER",
        "               _         _  'This Product  Discontinued'  _                 _                           spoke",
        "",
    ],
}


@dataclass
class AsciiArtStore:
    directories: list[Path] = field(default_factory=list)
    builtin: dict[str, list[str]] = field(default_factory=lambda: BUILTIN_ART)
    max_lines: int = 80

    @classmethod
    def default(cls, directory: Path | None = None) -> "AsciiArtStore":
        directories = [directory] if directory is not None else []
        return cls(directories=directories)

    def handle(self, text: str) -> list[str] | None:
        stripped = text.strip()
        if not stripped.lower().startswith("!ascii"):
            return None
        parts = stripped.split(maxsplit=1)
        if len(parts) != 2 or not parts[1].strip():
            return ["Usage: !ascii <name>"]
        return self.get(parts[1].strip())

    def get(self, name: str) -> list[str]:
        if "/" in name or "\\" in name or ".." in name:
            return [f"No such file: {name}.txt"]

        filename = f"{name}.txt"
        for directory in self.directories:
            path = directory / filename
            if path.is_file():
                return path.read_text(encoding="utf-8", errors="replace").splitlines()[: self.max_lines]

        art = self.builtin.get(name)
        if art is None:
            return [f"No such file: {filename}"]
        return art[: self.max_lines]
