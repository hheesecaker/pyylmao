from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


BOLD_ITALIC_MAP = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    "𝑨𝑩𝑪𝑫𝑬𝑭𝑮𝑯𝑰𝑱𝑲𝑳𝑴𝑵𝑶𝑷𝑸𝑹𝑺𝑻𝑼𝑽𝑾𝑿𝒀𝒁"
    "𝒂𝒃𝒄𝒅𝒆𝒇𝒈𝒉𝒊𝒋𝒌𝒍𝒎𝒏𝒐𝒑𝒒𝒓𝒔𝒕𝒖𝒗𝒘𝒙𝒚𝒛",
)


@dataclass(frozen=True)
class LLMPriceRow:
    provider: str
    input_per_mtok: Decimal
    output_per_mtok: Decimal
    cache_read_per_mtok: Decimal | None = None
    cache_write_per_mtok: Decimal | None = None


class ModelPriceProvider(Protocol):
    def models(self) -> list[dict]:
        ...


class OpenRouterModelPriceProvider:
    def __init__(self, url: str = "https://openrouter.ai/api/v1/models"):
        self.url = url
        self._models: list[dict] | None = None

    def models(self) -> list[dict]:
        if self._models is not None:
            return self._models
        request = urllib.request.Request(
            self.url,
            headers={
                "Accept": "application/json",
                "User-Agent": "pyylmao/0.1",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMPricesError(f"OpenRouter HTTP {exc.code}: {detail[:200]}") from exc
        except OSError as exc:
            raise LLMPricesError(f"OpenRouter error: {exc}") from exc
        self._models = list(payload.get("data") or [])
        return self._models


class LLMPricesError(Exception):
    pass


STATIC_PRICES: dict[str, list[LLMPriceRow]] = {
    "gpt-3.5-turbo": [
        LLMPriceRow("azure", Decimal("1.5"), Decimal("2")),
        LLMPriceRow("openai", Decimal("0.5"), Decimal("1.5")),
        LLMPriceRow("openrouter", Decimal("0.5"), Decimal("1.5")),
    ],
    "grok-4": [
        LLMPriceRow("x-ai", Decimal("3"), Decimal("15"), Decimal("0.75")),
    ],
    "grok-4-fast": [
        LLMPriceRow("openrouter/x-ai", Decimal("0.2"), Decimal("0.5"), Decimal("0.05")),
    ],
    "grok-4.1-fast": [
        LLMPriceRow("openrouter/x-ai", Decimal("0.2"), Decimal("0.5"), Decimal("0.05")),
    ],
    "gemini-3-flash-preview": [
        LLMPriceRow("openrouter/google", Decimal("0.5"), Decimal("3"), Decimal("0.05")),
    ],
    "claude-haiku-4.5": [
        LLMPriceRow("anthropic", Decimal("1"), Decimal("5"), Decimal("0.1"), Decimal("1.25")),
    ],
    "glm-4.7": [
        LLMPriceRow("openrouter/z-ai", Decimal("0.4"), Decimal("1.5")),
    ],
    "gpt-5": [
        LLMPriceRow("azure", Decimal("1.25"), Decimal("10"), Decimal("0.125")),
        LLMPriceRow("openai", Decimal("1.25"), Decimal("10"), Decimal("0.125")),
    ],
}


def is_llm_prices_command(text: str) -> bool:
    return bool(re.match(r"^\$llm\s+\S", text.strip(), flags=re.IGNORECASE))


def render_llm_prices_command(
    text: str,
    provider: ModelPriceProvider | None = None,
) -> list[str]:
    if not is_llm_prices_command(text):
        return ["Usage: $llm <model>"]
    query = parse_model_query(text)
    static_rows = STATIC_PRICES.get(query.lower())
    if static_rows is not None:
        return render_price_result(query, static_rows)

    provider = provider or OpenRouterModelPriceProvider()
    rows = rows_from_openrouter(query, provider.models())
    if not rows:
        return [
            "Fetching OpenRouter model data...",
            f"no matches for model '{query}'",
        ]
    return [
        "Fetching OpenRouter model data...",
        *render_price_result(query, rows),
    ]


def parse_model_query(text: str) -> str:
    rest = text.strip().split(maxsplit=1)[1].strip()
    return rest.split()[-1].strip("'\"").lower()


def rows_from_openrouter(query: str, models: list[dict]) -> list[LLMPriceRow]:
    normalized = query.lower()
    for model in models:
        model_id = str(model.get("id") or "")
        model_slug = str(model.get("canonical_slug") or "")
        model_name = str(model.get("name") or "")
        if not exact_model_match(normalized, model_id, model_slug, model_name):
            continue
        pricing = model.get("pricing") or {}
        provider = model_id.split("/", 1)[0] if "/" in model_id else "openrouter"
        return [
            LLMPriceRow(
                provider=f"openrouter/{provider}",
                input_per_mtok=price_per_mtok(pricing.get("prompt")),
                output_per_mtok=price_per_mtok(pricing.get("completion")),
                cache_read_per_mtok=optional_price_per_mtok(pricing.get("input_cache_read")),
                cache_write_per_mtok=optional_price_per_mtok(pricing.get("input_cache_write")),
            )
        ]
    return []


def exact_model_match(query: str, model_id: str, model_slug: str, model_name: str) -> bool:
    candidates = {
        model_id.lower(),
        model_id.rsplit("/", 1)[-1].lower(),
        model_slug.lower(),
        model_slug.rsplit("/", 1)[-1].lower(),
        slugify(model_name),
    }
    return query in candidates


def price_per_mtok(value: object) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value)) * Decimal("1000000")


def optional_price_per_mtok(value: object) -> Decimal | None:
    price = price_per_mtok(value)
    if price == 0:
        return None
    return price


def render_price_result(query: str, rows: list[LLMPriceRow]) -> list[str]:
    return [
        f"{bold_italic('llm-prices for')} '{bold_italic(query)}'",
        "",
        *render_price_table(rows),
        "",
        "",
    ]


def render_price_table(rows: list[LLMPriceRow]) -> list[str]:
    headers = ["Provider", "In $/MTok", "Out $/MTok"]
    table_rows = [
        [row.provider, format_dollars(row.input_per_mtok), format_dollars(row.output_per_mtok)]
        for row in rows
    ]
    if any(row.cache_read_per_mtok is not None for row in rows):
        headers.append("Cache Read $/MTok")
        for idx, row in enumerate(rows):
            table_rows[idx].append(
                "" if row.cache_read_per_mtok is None else format_dollars(row.cache_read_per_mtok)
            )
    if any(row.cache_write_per_mtok is not None for row in rows):
        headers.append("Cache Write $/MTok")
        for idx, row in enumerate(rows):
            table_rows[idx].append(
                "" if row.cache_write_per_mtok is None else format_dollars(row.cache_write_per_mtok)
            )
    return render_pipe_table(headers, table_rows)


def render_pipe_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    widths = [len(header) for header in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    def render_row(row: list[str]) -> str:
        cells = [cell.ljust(widths[idx]) for idx, cell in enumerate(row)]
        return " " + " | ".join(cells) + " "

    return [render_row(headers), *[render_row(row) for row in rows]]


def format_dollars(value: Decimal) -> str:
    normalized = value.normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"${text}"


def bold_italic(text: str) -> str:
    return text.translate(BOLD_ITALIC_MAP)


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
