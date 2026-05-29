from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol

from .formatting import compact_money
from .vtrade import normalize_ticker


@dataclass(frozen=True)
class StockPoint:
    timestamp: int
    close: Decimal

    @property
    def day_label(self) -> str:
        return datetime.fromtimestamp(self.timestamp, tz=timezone.utc).strftime("%d")


class StockHistoryProvider(Protocol):
    def history(self, ticker: str, period: str) -> list[StockPoint]:
        ...


class YahooStockHistoryProvider:
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
        self.cache: dict[tuple[str, str], tuple[float, list[StockPoint]]] = {}

    def history(self, ticker: str, period: str) -> list[StockPoint]:
        ticker = normalize_ticker(ticker)
        key = (ticker, period)
        now = time.time()
        cached = self.cache.get(key)
        if cached and now - cached[0] < 300:
            return cached[1]

        chart_range, interval = yahoo_period(period)
        yahoo_ticker = urllib.parse.quote(ticker, safe="")
        query = urllib.parse.urlencode({"range": chart_range, "interval": interval})
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_ticker}?{query}"
        request = urllib.request.Request(url, headers={"User-Agent": "pyylmao/0.1"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        result = payload["chart"]["result"][0]
        timestamps = result.get("timestamp") or []
        quote = result.get("indicators", {}).get("quote", [{}])[0]
        closes = quote.get("close") or []
        points = [
            StockPoint(int(ts), Decimal(str(close)))
            for ts, close in zip(timestamps, closes)
            if close is not None
        ]
        if not points:
            raise ValueError(f"No chart data for {ticker}")
        self.cache[key] = (now, points)
        return points


class StockCommandError(Exception):
    pass


def render_stock_command(
    text: str,
    provider: StockHistoryProvider | None = None,
) -> list[str]:
    match = re.match(r"^!stock\s+([a-zA-Z.]{1,10})(?:\s+(.+))?$", text.strip())
    if not match:
        return ["Usage: !stock <ticker> [days|all]"]
    display_ticker = match.group(1)
    options = parse_stock_options(match.group(2) or "")
    provider = provider or YahooStockHistoryProvider()
    try:
        points = provider.history(display_ticker, options.period)
    except Exception as exc:
        raise StockCommandError(f"Could not fetch chart for {display_ticker}: {exc}") from exc
    return render_stock_chart(display_ticker, points, options.label, options.width)


@dataclass(frozen=True)
class StockOptions:
    period: str
    label: str
    width: int


def parse_stock_options(raw: str) -> StockOptions:
    arg = raw.strip().split(maxsplit=1)[0].lower() if raw.strip() else ""
    if not arg:
        return StockOptions(period="30d", label="Past 30 Days", width=30)
    if arg in {"all", "max", "alltime", "all-time"}:
        return StockOptions(period="max", label="All Time", width=90)
    if arg.isdigit():
        value = max(1, int(arg))
        if value >= 60:
            return StockOptions(period="max", label="All Time", width=max(30, min(value, 160)))
        return StockOptions(period=f"{value}d", label=f"Past {value} Days", width=30)
    raise StockCommandError("Usage: !stock <ticker> [days|all]")


def yahoo_period(period: str) -> tuple[str, str]:
    if period == "max":
        return "max", "1mo"
    if not period.endswith("d"):
        return "1mo", "1d"
    days = int(period[:-1])
    if days <= 31:
        return "1mo", "1d"
    if days <= 90:
        return "3mo", "1d"
    if days <= 180:
        return "6mo", "1d"
    if days <= 365:
        return "1y", "1d"
    if days <= 730:
        return "2y", "1wk"
    return "max", "1mo"


def render_stock_chart(
    ticker: str,
    points: list[StockPoint],
    label: str,
    width: int = 30,
    rows: int = 8,
) -> list[str]:
    samples = resample_points(points, width)
    values = [point.close for point in samples]
    low = min(values)
    high = max(values)
    lines = [
        f"Trading Prices for {ticker} ({label}):",
        f"Price range: {compact_money(low)} - {compact_money(high)}",
        "",
    ]
    if high == low:
        graph = ["█" * width for _ in range(rows)]
        labels = [high for _ in range(rows)]
    else:
        span = high - low
        step = span / Decimal(rows)
        labels = [high - (step * index) for index in range(rows)]
        graph = [price_row(values, low + step * (rows - index - 1), step) for index in range(rows)]
    for label_value, graph_line in zip(labels, graph):
        lines.append(f"{compact_money(label_value):>7} {graph_line}")
    lines.append("-" * (8 + width))
    lines.append(date_axis(samples, width))
    return lines


def price_row(values: list[Decimal], floor: Decimal, step: Decimal) -> str:
    blocks = " ▁▂▃▄▅▆▇█"
    chars = []
    ceiling = floor + step
    for value in values:
        if value >= ceiling:
            chars.append("█")
        elif value <= floor:
            chars.append(" ")
        else:
            ratio = (value - floor) / step
            index = int((ratio * Decimal("8")).to_integral_value(rounding="ROUND_FLOOR"))
            chars.append(blocks[max(1, min(index, 8))])
    return "".join(chars)


def resample_points(points: list[StockPoint], width: int) -> list[StockPoint]:
    if not points:
        raise ValueError("No chart data")
    if len(points) >= width:
        return [points[round(index * (len(points) - 1) / (width - 1))] for index in range(width)]
    return points + [points[-1]] * (width - len(points))


def date_axis(points: list[StockPoint], width: int) -> str:
    if not points:
        return ""
    slots = 10
    indexes = [round(index * (len(points) - 1) / (slots - 1)) for index in range(slots)]
    labels = [points[index].day_label for index in indexes]
    return " " * 8 + " ".join(labels)
