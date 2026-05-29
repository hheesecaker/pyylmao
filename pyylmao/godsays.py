from __future__ import annotations

import random
import re
import secrets
from collections.abc import Callable, Sequence


DEFAULT_WORD_COUNT = 20
MAX_WORD_COUNT = 40

WORD_BANK: tuple[str, ...] = (
    "finger",
    "Darren",
    "EUR",
    "books",
    "VII",
    "umbered",
    "precursor",
    "taxi",
    "DN",
    "epilepsy",
    "tics",
    "Massacre",
    "overcame",
    "Delete",
    "dispatch",
    "collisions",
    "Structure",
    "largely",
    "Minecraft",
    "allegations",
    "lantern",
    "packet",
    "chlorine",
    "spline",
    "Byzantine",
    "muffler",
    "archive",
    "radar",
    "peacock",
    "throttle",
    "dentist",
    "paradox",
    "Velcro",
    "molecule",
    "invoice",
    "cactus",
    "subroutine",
    "marble",
    "preface",
    "haywire",
    "nebula",
    "carbonate",
    "postal",
    "tambourine",
    "kernel",
    "solder",
    "laminate",
    "vortex",
    "accordion",
    "algebra",
    "monolith",
    "satellite",
    "junction",
    "porcelain",
    "cricket",
    "magnet",
    "altitude",
    "gasket",
    "pilgrim",
    "fractal",
)

MEANINGS: tuple[str, ...] = (
    "The collection of seemingly unrelated words is a deliberately chaotic jumble that suggests a hidden message only after the pattern has already fallen apart.",
    "This reads like an oracle made from broken autocomplete: absurd on the surface, but pointing toward confusion being treated as prophecy.",
    "The phrase is nonsense arranged with enough confidence to feel symbolic, which is usually how bad omens introduce themselves.",
    "It is a scrambled proverb about systems failing in public while everyone pretends the random parts still belong together.",
)


def is_godsays_command(text: str) -> bool:
    return bool(re.match(r"^!godsays\s*(\d*)$", text.strip(), flags=re.IGNORECASE))


def render_godsays_command(
    text: str,
    *,
    rng: random.Random | None = None,
    meaning_provider: Callable[[Sequence[str]], str] | None = None,
) -> list[str]:
    count = parse_godsays_count(text)
    words = choose_words(count, rng)
    meaning = (
        meaning_provider(words).strip()
        if meaning_provider is not None
        else default_meaning(words, rng)
    )
    return [format_godsays_words(words), f"Meaning: {meaning}"]


def parse_godsays_count(text: str) -> int:
    match = re.match(r"^!godsays\s*(\d*)$", text.strip(), flags=re.IGNORECASE)
    if not match:
        raise ValueError("Usage: !godsays [count]")
    raw = match.group(1)
    if not raw:
        return DEFAULT_WORD_COUNT
    return max(1, min(int(raw), MAX_WORD_COUNT))


def choose_words(count: int, rng: random.Random | None = None) -> list[str]:
    source = rng or secrets.SystemRandom()
    return [source.choice(WORD_BANK) for _ in range(count)]


def default_meaning(words: Sequence[str], rng: random.Random | None = None) -> str:
    source = rng or secrets.SystemRandom()
    return source.choice(MEANINGS)


def format_godsays_words(words: Sequence[str]) -> str:
    return '" ' + "  ".join(words) + '"'
