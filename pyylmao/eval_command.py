from __future__ import annotations

import builtins
import contextlib
import io
import re
from typing import Any


pattern = r"(?i)\beval\b\s*(.*)"
EVAL_RE = re.compile(pattern)

_BASE_BUILTINS = dict(vars(builtins))
_EVAL_BUILTINS = dict(_BASE_BUILTINS)


def is_eval_command(text: str) -> bool:
    return bool(EVAL_RE.search(text.strip()))


def render_eval_command(
    text: str,
    channel: str,
    nickname: str,
    username: str = "",
    hostname: str = "",
) -> list[str]:
    match = EVAL_RE.search(text.strip())
    if not match:
        return []
    return entrypoint([match.group(1)], channel, nickname, username, hostname)


def entrypoint(
    args: list[str],
    channel: str,
    nickname: str,
    username: str,
    hostname: str,
) -> list[str]:
    expression = args[0] if args else ""
    namespace = _fresh_namespace(
        args=[expression],
        channel=channel,
        nickname=nickname,
        username=username,
        hostname=hostname,
    )
    stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout):
            result = eval(expression, namespace, namespace)
    except Exception as exc:
        printed = _split_visible(stdout.getvalue())
        return [*printed, f"Eval error: {exc}"]
    return [*_split_visible(stdout.getvalue()), *_split_visible(str(result))]


def reset_eval_builtins_for_tests() -> None:
    _EVAL_BUILTINS.clear()
    _EVAL_BUILTINS.update(_BASE_BUILTINS)


def _fresh_namespace(
    *,
    args: list[str],
    channel: str,
    nickname: str,
    username: str,
    hostname: str,
) -> dict[str, Any]:
    namespace: dict[str, Any] = {}
    namespace["__name__"] = "pyylmao.commands.eval.ins_reconstructed"
    namespace["__file__"] = "/usr/src/app/src/commands/eval/__init__.py"
    namespace["__package__"] = "pyylmao.commands.eval"
    namespace["__builtins__"] = _EVAL_BUILTINS
    namespace["channel"] = channel
    namespace["nickname"] = nickname
    namespace["username"] = username
    namespace["hostname"] = hostname
    namespace["args"] = args
    namespace["pattern"] = pattern
    namespace["entrypoint"] = entrypoint
    return namespace


def _split_visible(text: str) -> list[str]:
    lines = [line for line in str(text).splitlines() if line]
    if lines:
        return lines
    if text:
        return [text]
    return []
