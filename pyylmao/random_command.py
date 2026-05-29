from __future__ import annotations

import random as rand_module
import re
from typing import Protocol


pattern = r"^\.random\s*(.*)$"


class RandomSource(Protocol):
    def randint(self, a: int, b: int) -> int:
        ...


def is_random_command(text: str) -> bool:
    return re.match(pattern, text.strip()) is not None


def render_random_command(
    text: str,
    rng: RandomSource | None = None,
) -> list[str]:
    match = re.match(pattern, text.strip())
    if not match:
        return []
    return [format_random_response(match.group(1), rng or rand_module)]


def random_command(bot, args):
    del bot
    return format_random_response(args, rand_module)


def entrypoint(args, channel, nickname, username, hostname):
    del channel, nickname, username, hostname
    print(format_random_response(" ".join(str(arg) for arg in args), rand_module))


def format_random_response(args: str, rng: RandomSource) -> str:
    args = args.strip()

    if not args:
        num = rng.randint(1, 100)
        return f"Random number: {num}"

    parts = args.split()

    try:
        if len(parts) == 1:
            min_val = 1
            max_val = int(parts[0])
        elif len(parts) == 2:
            min_val = int(parts[0])
            max_val = int(parts[1])
        else:
            return "Usage: .random [min max] or .random [max]"

        if min_val > max_val:
            return "Error: min cannot be greater than max"

        num = rng.randint(min_val, max_val)
        return f"Random number between {min_val} and {max_val}: {num}"

    except ValueError:
        return "Error: Please provide valid numbers"


command = random_command
