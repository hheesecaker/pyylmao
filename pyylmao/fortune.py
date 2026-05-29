from __future__ import annotations

import random
import re
import textwrap
from collections.abc import Sequence


SOLID_LINE = "▀▀▀▀▀▀▀▀▀▀"
BROKEN_LINE = "▀▀▀▀  ▀▀▀▀"

TRIGRAM_ORDER = ("heaven", "lake", "fire", "thunder", "wind", "water", "mountain", "earth")
TRIGRAM_LINES = {
    "heaven": (True, True, True),
    "lake": (True, True, False),
    "fire": (True, False, True),
    "thunder": (True, False, False),
    "wind": (False, True, True),
    "water": (False, True, False),
    "mountain": (False, False, True),
    "earth": (False, False, False),
}

KING_WEN_BY_LOWER_UPPER = (
    (1, 43, 14, 34, 9, 5, 26, 11),
    (10, 58, 38, 54, 61, 60, 41, 19),
    (13, 49, 30, 55, 37, 63, 22, 36),
    (25, 17, 21, 51, 42, 3, 27, 24),
    (44, 28, 50, 32, 57, 48, 18, 46),
    (6, 47, 64, 40, 59, 29, 4, 7),
    (33, 31, 56, 62, 53, 39, 52, 15),
    (12, 45, 35, 16, 20, 8, 23, 2),
)

HEXAGRAM_NAMES = {
    1: "The Creative",
    2: "The Receptive",
    3: "Difficulty at the Beginning",
    4: "Youthful Folly",
    5: "Waiting",
    6: "Conflict",
    7: "The Army",
    8: "Holding Together",
    9: "The Taming Power of the Small",
    10: "Treading",
    11: "Peace",
    12: "Standstill",
    13: "Fellowship with Men",
    14: "Possession in Great Measure",
    15: "Modesty",
    16: "Enthusiasm",
    17: "Following",
    18: "Work on What Has Been Spoiled",
    19: "Approach",
    20: "Contemplation",
    21: "Biting Through",
    22: "Grace",
    23: "Splitting Apart",
    24: "Return",
    25: "Innocence",
    26: "Taming the Power of the Great",
    27: "Nourishment",
    28: "Preponderance of the Great",
    29: "The Abysmal",
    30: "The Clinging",
    31: "Influence",
    32: "Duration",
    33: "Retreat",
    34: "The Power of the Great",
    35: "Progress",
    36: "Darkening of the Light",
    37: "The Family",
    38: "Opposition",
    39: "Obstruction",
    40: "Deliverance",
    41: "Decrease",
    42: "Increase",
    43: "Breakthrough",
    44: "Coming to Meet",
    45: "Gathering Together",
    46: "Pushing Upward",
    47: "Oppression",
    48: "The Well",
    49: "Revolution",
    50: "The Cauldron",
    51: "The Arousing",
    52: "Keeping Still",
    53: "Development",
    54: "The Marrying Maiden",
    55: "Abundance",
    56: "The Wanderer",
    57: "Gentle Penetration",
    58: "The Joyous",
    59: "Dispersion",
    60: "Limitation",
    61: "Inner Truth",
    62: "Preponderance of the Small",
    63: "After Completion",
    64: "Before Completion",
}

HEXAGRAM_MEANINGS = {
    1: "pure, dynamic potential and the strong initiating force of creative energy",
    2: "receptivity, patience, and the power of yielding to the shape of events",
    3: "early difficulty, confusion, and the need to organize before pushing ahead",
    4: "inexperience, instruction, and learning through direct correction",
    5: "waiting, nourishment, and trusting timing before decisive action",
    6: "dispute, friction, and the need for clarity before conflict hardens",
    7: "discipline, collective force, and leadership under pressure",
    8: "unity, trust, and the importance of choosing sound alliances",
    9: "small restraint, gradual refinement, and accumulating influence bit by bit",
    10: "careful conduct, respect for danger, and stepping with awareness",
    11: "harmony, balance, and natural order moving into cooperation",
    12: "stagnation, separation, and a time when direct advance may not land",
    13: "fellowship, shared purpose, and openness beyond narrow loyalties",
    14: "great possession, clarity, and the responsibility that comes with abundance",
    15: "modesty, balance, and strength expressed without display",
    16: "enthusiasm, momentum, and music or vision gathering people into motion",
    17: "following, adaptation, and finding the right current to move with",
    18: "repair, corruption addressed, and work on what has been spoiled",
    19: "approach, guidance, and a favorable movement toward what needs attention",
    20: "contemplation, observation, and seeing the pattern before acting",
    21: "biting through, judgment, and cutting through an obstruction",
    22: "grace, form, and the surface beauty that can clarify or distract",
    23: "splitting apart, erosion, and letting the unsound part fall away",
    24: "return, renewal, and the first movement back toward the path",
    25: "innocence, spontaneity, and acting without contrivance",
    26: "restraint, accumulated strength, and disciplined use of power",
    27: "nourishment, speech, and choosing what feeds body and mind",
    28: "great excess, strain, and a beam carrying more than ordinary weight",
    29: "repeated danger, depth, and courage under recurring uncertainty",
    30: "clarity, attachment, and the fire that illuminates by clinging to fuel",
    31: "influence, attraction, and mutual responsiveness",
    32: "duration, steadiness, and the power of continuing without drift",
    33: "retreat, strategic withdrawal, and conserving position",
    34: "great power, vigor, and the need to keep force aligned with right action",
    35: "progress, visibility, and advancement under a rising light",
    36: "darkening of the light, concealment, and protecting clarity in hostile conditions",
    37: "family order, roles, and responsibility within a household or close system",
    38: "opposition, difference, and learning to work with estrangement",
    39: "obstruction, difficulty, and seeking help rather than forcing the blocked road",
    40: "release, relief, and the loosening of a knot after tension",
    41: "decrease, simplification, and offering up what is not essential",
    42: "increase, blessing, and growth that should be directed generously",
    43: "breakthrough, declaration, and resolving what has become intolerable",
    44: "encounter, sudden contact, and caution around a powerful influence",
    45: "gathering, assembly, and the force of people or resources converging",
    46: "pushing upward, steady ascent, and patient advancement",
    47: "oppression, exhaustion, and maintaining speech and spirit under constraint",
    48: "the well, shared sources, and the need to maintain what everyone draws from",
    49: "revolution, renewal, and changing the form when the time is ripe",
    50: "the cauldron, transformation, and culture formed through preparation",
    51: "shock, arousal, and the thunderclap that wakes attention",
    52: "keeping still, stillness, and stopping movement at the right place",
    53: "development, gradual progress, and maturation through proper stages",
    54: "a secondary position, adaptation, and limits that must be acknowledged",
    55: "abundance, fullness, and a peak moment that still requires awareness",
    56: "wandering, transience, and careful conduct while away from home ground",
    57: "gentle penetration, subtle influence, and gradual transformation",
    58: "joy, openness, and exchange that encourages connection",
    59: "dispersion, dissolution, and scattering what has become rigid",
    60: "limitation, measure, and finding the boundary that makes flow useful",
    61: "inner truth, sincerity, and clarity that comes from honest self-examination",
    62: "small excess, careful detail, and success through modest, precise action",
    63: "after completion, a settled order that still needs vigilance",
    64: "before completion, transition, and care before the final crossing",
}

HEXAGRAM_BY_LINES: dict[tuple[bool, ...], int] = {}
for lower_index, lower_name in enumerate(TRIGRAM_ORDER):
    for upper_index, upper_name in enumerate(TRIGRAM_ORDER):
        lines = TRIGRAM_LINES[lower_name] + TRIGRAM_LINES[upper_name]
        HEXAGRAM_BY_LINES[lines] = KING_WEN_BY_LOWER_UPPER[lower_index][upper_index]

MONOSPACE_TRANS = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    "𝙰𝙱𝙲𝙳𝙴𝙵𝙶𝙷𝙸𝙹𝙺𝙻𝙼𝙽𝙾𝙿𝚀𝚁𝚂𝚃𝚄𝚅𝚆𝚇𝚈𝚉𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿",
)


def is_fortune_command(text: str) -> bool:
    return parse_fortune_prompt(text) is not None


def parse_fortune_prompt(text: str) -> str | None:
    match = re.match(r"^!fortune(?:\s+(.*))?$", text.strip(), flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return (match.group(1) or "").strip()


def render_fortune_command(text: str, throws: Sequence[int] | None = None) -> list[str]:
    prompt = parse_fortune_prompt(text)
    if prompt is None:
        return []
    if throws is None:
        throws = throw_stalks()
    if len(throws) != 6 or any(throw not in {6, 7, 8, 9} for throw in throws):
        raise ValueError("fortune throws must be six values drawn from 6, 7, 8, and 9")

    primary_lines = tuple(throw in {7, 9} for throw in throws)
    changed_lines = tuple(
        not line if throw in {6, 9} else line
        for line, throw in zip(primary_lines, throws, strict=True)
    )
    primary_number = HEXAGRAM_BY_LINES[primary_lines]
    changed_number = HEXAGRAM_BY_LINES[changed_lines]
    has_changes = primary_lines != changed_lines

    if has_changes:
        title = (
            f"{primary_number} {hexagram_symbol(primary_number)} changing to "
            f"{changed_number} {hexagram_symbol(changed_number)} "
        )
    else:
        title = f"{primary_number} {hexagram_symbol(primary_number)} "

    lines = [f"{title:^49}", "", ""]
    lines.extend(render_hexagram_body(primary_lines, primary_number, prompt, changed_lines, changed_number))
    lines.append("")
    lines.append("stalks thrown: " + " ".join(str(throw) for throw in throws))
    return lines


def throw_stalks(rng: random.Random | None = None) -> list[int]:
    chooser = rng or random.SystemRandom()
    return [chooser.choices((6, 7, 8, 9), weights=(1, 5, 7, 3), k=1)[0] for _ in range(6)]


def hexagram_symbol(number: int) -> str:
    return chr(0x4DBF + number)


def render_hexagram_body(
    primary_lines: Sequence[bool],
    primary_number: int,
    prompt: str,
    changed_lines: Sequence[bool] | None = None,
    changed_number: int | None = None,
) -> list[str]:
    right_art = line_art(changed_lines) if changed_lines is not None and changed_number != primary_number else None
    wrap_width = 62 if right_art else 66
    text_lines = textwrap.wrap(interpretation(primary_number, prompt, changed_number), width=wrap_width)
    left_art = line_art(primary_lines)

    rendered: list[str] = []
    for index, art in enumerate(left_art):
        text = text_lines[index] if index < len(text_lines) else ""
        if right_art:
            rendered.append(f"{art}  {text:<{wrap_width}}  {right_art[index]}")
        else:
            rendered.append(f"{art}  {text}")
    for text in text_lines[len(left_art) :]:
        rendered.append(f"{'':12}{text}")
    return rendered


def line_art(lines: Sequence[bool]) -> list[str]:
    return [SOLID_LINE if line else BROKEN_LINE for line in reversed(lines)]


def interpretation(primary_number: int, prompt: str, changed_number: int | None = None) -> str:
    primary = hexagram_phrase(primary_number)
    if changed_number is None or changed_number == primary_number:
        text = f"{primary} represents {HEXAGRAM_MEANINGS[primary_number]}."
    else:
        changed = hexagram_phrase(changed_number)
        text = (
            f"{primary} suggests {HEXAGRAM_MEANINGS[primary_number]}. "
            f"{changed} points toward {HEXAGRAM_MEANINGS[changed_number]}."
        )
    if prompt:
        text += (
            f" In relation to the meditation '{prompt}', the reading advises "
            "watching the pattern carefully and acting with the hexagrams' timing."
        )
    return text


def hexagram_phrase(number: int) -> str:
    name = HEXAGRAM_NAMES[number].upper()
    return f'{monospace("HEXAGRAM " + str(number))}, "{monospace(name)},"'


def monospace(text: str) -> str:
    return text.upper().translate(MONOSPACE_TRANS)
