from __future__ import annotations

from decimal import Decimal
from typing import Any

from ...llm import LLMResult, decimal_cost, format_cents, response_cost_usd, stats_line
from ...state import JsonState


TOTAL_COST_KEY = "commands.gpt.billing.total_cost_usd"


def cents(value_usd: Decimal | float | int | str) -> str:
    return format_cents(Decimal(str(value_usd)))


def cost_from_response(payload: dict[str, Any]) -> Decimal | None:
    return response_cost_usd(payload)


def add_cost(state: JsonState, value_usd: Decimal | float | int | str) -> Decimal:
    amount = Decimal(str(value_usd))
    root = state.data.setdefault("kvstore", {})
    current: Any = root
    parts = TOTAL_COST_KEY.split(".")
    for part in parts[:-1]:
        if not isinstance(current, dict):
            current = {}
        current = current.setdefault(part, {})
    previous = decimal_cost(current.get(parts[-1])) or Decimal("0")
    total = previous + amount
    current[parts[-1]] = str(total)
    state.save()
    return total


__all__ = [
    "LLMResult",
    "TOTAL_COST_KEY",
    "add_cost",
    "cents",
    "cost_from_response",
    "decimal_cost",
    "format_cents",
    "response_cost_usd",
    "stats_line",
]
