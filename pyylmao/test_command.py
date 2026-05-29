from __future__ import annotations

import random
import re
from collections.abc import Callable


CodeProvider = Callable[[], int]


def is_test_command(text: str) -> bool:
    return parse_test_args(text) is not None


def render_test_command(text: str, code_provider: CodeProvider | None = None) -> list[str]:
    args = parse_test_args(text)
    if args is None:
        return []
    if code_provider is None:
        code_provider = default_code_provider
    code = code_provider()
    return ["your args:"] + [f"{index} - {arg}" for index, arg in enumerate(args)] + [
        f"relay this code in your response: {code:04d}"
    ]


def parse_test_args(text: str) -> list[str] | None:
    match = re.match(r"^!test\s+(.+)$", text.strip(), flags=re.DOTALL)
    if not match:
        return None
    return match.group(1).split()


def default_code_provider() -> int:
    return random.SystemRandom().randrange(1000, 10000)
