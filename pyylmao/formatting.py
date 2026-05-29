from __future__ import annotations

import re
import textwrap
from decimal import Decimal


NICK_PREFIXES = "@+%~&"


def clean_nick(nick: str) -> str:
    return nick.lstrip(NICK_PREFIXES)


def money(value: float | Decimal, currency: str = "USD") -> str:
    amount = Decimal(str(value))
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    return f"{sign}${amount:,.2f} {currency}"


def compact_money(value: float | Decimal) -> str:
    amount = Decimal(str(value))
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    return f"{sign}${amount:,.2f}"


def quantity(value: float | Decimal) -> str:
    amount = Decimal(str(value)).normalize()
    text = format(amount, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def split_irc_lines(text: str, width: int = 390) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines() or [""]:
        if len(raw) <= width:
            lines.append(raw)
            continue
        wrapped = textwrap.wrap(
            raw,
            width=width,
            break_long_words=True,
            break_on_hyphens=False,
            replace_whitespace=False,
            drop_whitespace=False,
        )
        lines.extend(wrapped or [""])
    return lines


def table(headers: list[str], rows: list[list[str]], align_right: set[int] | None = None) -> list[str]:
    align_right = align_right or set()
    widths = [len(header) for header in headers]
    for row in rows:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(value))

    def fmt_cell(idx: int, value: str) -> str:
        if idx in align_right:
            return value.rjust(widths[idx])
        return value.ljust(widths[idx])

    top = "╭" + "┬".join("─" * (width + 2) for width in widths) + "╮"
    sep = "├" + "┼".join("─" * (width + 2) for width in widths) + "┤"
    bottom = "╰" + "┴".join("─" * (width + 2) for width in widths) + "╯"
    out = [top]
    out.append("│ " + " │ ".join(fmt_cell(i, h) for i, h in enumerate(headers)) + " │")
    out.append(sep)
    for row in rows:
        out.append("│ " + " │ ".join(fmt_cell(i, v) for i, v in enumerate(row)) + " │")
    out.append(bottom)
    return out


ITALIC_MAP = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    "𝘈𝘉𝘊𝘋𝘌𝘍𝘎𝘏𝘐𝘑𝘒𝘓𝘔𝘕𝘖𝘗𝘘𝘙𝘚𝘛𝘜𝘝𝘞𝘟𝘠𝘡"
    "𝘢𝘣𝘤𝘥𝘦𝘧𝘨𝘩𝘪𝘫𝘬𝘭𝘮𝘯𝘰𝘱𝘲𝘳𝘴𝘵𝘶𝘷𝘸𝘹𝘺𝘻",
)


def italic_title(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text.translate(ITALIC_MAP)
