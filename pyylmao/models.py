from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from .llm_prices import LLMPricesError, OpenRouterModelPriceProvider, optional_price_per_mtok


class ModelsProvider(Protocol):
    def models(self) -> list[dict]:
        ...


class ModelsCommandError(RuntimeError):
    pass


def is_models_command(text: str) -> bool:
    return text.strip().lower() == "!models"


def render_models_command(
    text: str,
    provider: ModelsProvider | None = None,
    limit: int = 20,
) -> list[str]:
    if not is_models_command(text):
        return ["Usage: !models"]
    provider = provider or OpenRouterModelPriceProvider()
    try:
        models = provider.models()
    except LLMPricesError as exc:
        raise ModelsCommandError(str(exc)) from exc

    rows = [model_row(model) for model in newest_models(models)[:limit]]
    if not rows:
        return ["No OpenRouter models found."]
    return [
        "OpenRouter models",
        render_row(("MODEL", "CTX", "IN", "OUT"), widths_for(rows)),
        *[render_row(row, widths_for(rows)) for row in rows],
    ]


def newest_models(models: list[dict]) -> list[dict]:
    return sorted(models, key=lambda model: int(model.get("created") or 0), reverse=True)


def model_row(model: dict) -> tuple[str, str, str, str]:
    pricing = model.get("pricing") or {}
    return (
        str(model.get("id") or model.get("name") or "?"),
        format_context(model.get("context_length")),
        format_price(optional_price_per_mtok(pricing.get("prompt"))),
        format_price(optional_price_per_mtok(pricing.get("completion"))),
    )


def widths_for(rows: list[tuple[str, ...]]) -> tuple[int, ...]:
    widths = [len("MODEL"), len("CTX"), len("IN"), len("OUT")]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))
    return tuple(widths)


def render_row(row: tuple[str, ...], widths: tuple[int, ...]) -> str:
    return " | ".join(cell.ljust(widths[idx]) for idx, cell in enumerate(row))


def format_context(value: object) -> str:
    try:
        context = int(str(value))
    except (TypeError, ValueError):
        return "?"
    if context >= 1000:
        if context % 1000 == 0:
            return f"{context // 1000}k"
        return f"{context / 1000:.1f}k"
    return str(context)


def format_price(value: Decimal | None) -> str:
    if value is None:
        return "-"
    normalized = value.normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"${text}"
