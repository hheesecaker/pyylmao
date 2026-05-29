from __future__ import annotations

import json
import re
from collections.abc import Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pyylmao.helpers import md2irc


pattern = r"^tcl cp (.+)$"

COINGECKO_IDS: dict[str, str] = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "ltc": "litecoin",
    "xrp": "ripple",
    "ada": "cardano",
    "doge": "dogecoin",
    "sol": "solana",
    "bnb": "binancecoin",
    "dot": "polkadot",
    "link": "chainlink",
    "matic": "matic-network",
    "avax": "avalanche-2",
    "trx": "tron",
    "xlm": "stellar",
    "bch": "bitcoin-cash",
    "xmr": "monero",
    "etc": "ethereum-classic",
    "atom": "cosmos",
    "fil": "filecoin",
    "near": "near",
    "apt": "aptos",
    "arb": "arbitrum",
    "op": "optimism",
    "ton": "the-open-network",
    "usdt": "tether",
    "usdc": "usd-coin",
    "dai": "dai",
    "pepe": "pepe",
    "shib": "shiba-inu",
    "wbtc": "wrapped-bitcoin",
    "uni": "uniswap",
    "aave": "aave",
    "inj": "injective-protocol",
    "sui": "sui",
    "hbar": "hedera-hashgraph",
    "icp": "internet-computer",
    "kas": "kaspa",
    "stx": "blockstack",
    "render": "render-token",
    "rndr": "render-token",
}

PriceFetcher = Callable[[list[str]], dict[str, float | int | str]]


class CryptoPriceError(Exception):
    pass


def is_cp_command(text: str) -> bool:
    return re.match(pattern, text.strip(), flags=re.IGNORECASE) is not None


def render_cp_command(
    text: str,
    fetcher: PriceFetcher | None = None,
) -> list[str]:
    match = re.match(pattern, text.strip(), flags=re.IGNORECASE)
    if not match:
        return []
    tickers = parse_tickers(match.group(1))
    if not tickers:
        return ["Usage: tcl cp <ticker> [ticker ...]"]
    prices = fetcher(tickers) if fetcher is not None else fetch_coingecko_prices(tickers)
    return render_cp_prices(tickers, prices)


def parse_tickers(text: str) -> list[str]:
    seen = set()
    tickers: list[str] = []
    for raw in re.split(r"[\s,]+", text.strip()):
        ticker = re.sub(r"[^A-Za-z0-9_:-]+", "", raw).lower()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        tickers.append(ticker)
    return tickers


def fetch_coingecko_prices(tickers: list[str]) -> dict[str, float | int | str]:
    ids = [COINGECKO_IDS[ticker] for ticker in tickers if ticker in COINGECKO_IDS]
    if not ids:
        return {}
    query = urlencode(
        {
            "ids": ",".join(dict.fromkeys(ids)),
            "vs_currencies": "usd",
        }
    )
    request = Request(
        f"https://api.coingecko.com/api/v3/simple/price?{query}",
        headers={"User-Agent": "pyylmao-cp/1.0"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = response.read().decode("utf-8", errors="replace")
    except OSError as exc:
        raise CryptoPriceError(f"Error fetching crypto prices: {exc}") from exc
    data = json.loads(payload)
    if not isinstance(data, dict):
        return {}
    prices: dict[str, float | int | str] = {}
    for ticker in tickers:
        coin_id = COINGECKO_IDS.get(ticker)
        row = data.get(coin_id) if coin_id else None
        if isinstance(row, dict) and "usd" in row:
            prices[ticker] = row["usd"]
    return prices


def render_cp_prices(
    tickers: list[str],
    prices: dict[str, float | int | str],
) -> list[str]:
    known_rows = []
    unknown = []
    for ticker in tickers:
        if ticker in prices:
            known_rows.append((ticker.upper(), format_usd(prices[ticker])))
        else:
            unknown.append(ticker.upper())
    if not known_rows and unknown:
        return ["Unknown tickers: " + ", ".join(unknown)]

    markdown = ["| Ticker | Price (USD) |", "|---|---:|"]
    for ticker, price in known_rows:
        markdown.append(f"| {ticker} | {price} |")
    output = md2irc("\n".join(markdown)).decode("utf-8", errors="replace")
    lines = output.splitlines()
    if unknown:
        lines.append("Unknown tickers: " + ", ".join(unknown))
    return lines


def format_usd(value: float | int | str) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return f"${value}"
    if number >= 1000:
        return f"${number:,.2f}"
    if number >= 1:
        return f"${number:,.2f}"
    return f"${number:.8f}".rstrip("0").rstrip(".")


def entrypoint(args, channel, nickname, username, hostname):
    del channel, nickname, username, hostname
    text = " ".join(str(arg) for arg in args)
    for line in render_cp_command(f"tcl cp {text}"):
        print(line)
