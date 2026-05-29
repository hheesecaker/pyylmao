from __future__ import annotations

import json
import random
import string
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Callable, Protocol

from .formatting import clean_nick, compact_money, money, quantity, table
from .state import JsonState


class PriceProvider(Protocol):
    def price(self, ticker: str) -> Decimal:
        ...


class FXProvider(Protocol):
    def rate(self, from_currency: str, to_currency: str) -> Decimal:
        ...


class StaticPriceProvider:
    def __init__(
        self,
        prices: dict[str, Decimal | float | str] | None = None,
        currencies: dict[str, str] | None = None,
    ):
        self.prices = {k.upper(): Decimal(str(v)) for k, v in (prices or {}).items()}
        self.currencies = {
            normalize_ticker(k): normalize_currency(v)
            for k, v in (currencies or {}).items()
        }

    def price(self, ticker: str) -> Decimal:
        ticker = normalize_ticker(ticker)
        return self.prices.get(ticker, Decimal("1"))

    def currency(self, ticker: str) -> str:
        return self.currencies.get(normalize_ticker(ticker), "USD")


class YahooPriceProvider:
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
        self.cache: dict[str, tuple[float, Decimal, str]] = {}

    def price(self, ticker: str) -> Decimal:
        return self.quote(ticker)[0]

    def currency(self, ticker: str) -> str:
        return self.quote(ticker)[1]

    def quote(self, ticker: str) -> tuple[Decimal, str]:
        ticker = normalize_ticker(ticker)
        now = time.time()
        cached = self.cache.get(ticker)
        if cached and now - cached[0] < 30:
            return cached[1], cached[2]

        yahoo_ticker = urllib.parse.quote(ticker, safe="")
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_ticker}?range=1d&interval=1m"
        request = urllib.request.Request(url, headers={"User-Agent": "pyylmao/0.1"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        result = payload["chart"]["result"][0]
        meta = result["meta"]
        raw = meta.get("regularMarketPrice") or meta.get("previousClose")
        if raw is None:
            quote = result.get("indicators", {}).get("quote", [{}])[0]
            closes = [item for item in quote.get("close", []) if item is not None]
            raw = closes[-1] if closes else None
        if raw is None:
            raise ValueError(f"No market price for {ticker}")
        price = Decimal(str(raw))
        currency = normalize_currency(str(meta.get("currency") or "USD"))
        self.cache[ticker] = (now, price, currency)
        return price, currency


class StaticFXProvider:
    def __init__(self, rates: dict[tuple[str, str], Decimal | float | str] | None = None):
        self.rates = {
            (normalize_currency(left), normalize_currency(right)): Decimal(str(value))
            for (left, right), value in (rates or {}).items()
        }

    def rate(self, from_currency: str, to_currency: str) -> Decimal:
        from_currency = normalize_currency(from_currency)
        to_currency = normalize_currency(to_currency)
        if from_currency == to_currency:
            return Decimal("1")
        direct = self.rates.get((from_currency, to_currency))
        if direct is not None:
            return direct
        inverse = self.rates.get((to_currency, from_currency))
        if inverse is not None and inverse != 0:
            return Decimal("1") / inverse
        raise ValueError(f"No FX rate for {from_currency} -> {to_currency}")


class FXRatesProvider:
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
        self.cache: dict[tuple[str, str], tuple[float, Decimal]] = {}

    def rate(self, from_currency: str, to_currency: str) -> Decimal:
        from_currency = normalize_currency(from_currency)
        to_currency = normalize_currency(to_currency)
        if from_currency == to_currency:
            return Decimal("1")
        key = (from_currency, to_currency)
        now = time.time()
        cached = self.cache.get(key)
        if cached and now - cached[0] < 300:
            return cached[1]

        query = urllib.parse.urlencode({"base": from_currency, "currencies": to_currency})
        url = f"https://api.fxratesapi.com/latest?{query}"
        request = urllib.request.Request(url, headers={"User-Agent": "pyylmao/0.1"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise ValueError(f"FX lookup failure ({from_currency}->{to_currency}): {exc}") from exc
        raw = (payload.get("rates") or {}).get(to_currency)
        if raw is None:
            raise ValueError(f"Could not determine FX rate for {from_currency} -> {to_currency}")
        rate = Decimal(str(raw))
        self.cache[key] = (now, rate)
        return rate


@dataclass(frozen=True)
class PendingTrade:
    nick: str
    alias: str
    side: str
    ticker: str
    qty: Decimal
    price: Decimal
    total: Decimal
    currency: str
    expires_at: float
    convert: bool = False
    convert_from: str | None = None
    convert_to: str | None = None
    convert_rate: Decimal | None = None
    convert_source_total: Decimal | None = None
    convert_fee: Decimal | None = None


CRYPTO_SUFFIX_CANDIDATES = {
    "ADA",
    "BONK",
    "BTC",
    "DOGE",
    "ETH",
    "FLOKI",
    "KAIA",
    "MOG",
    "PEPE",
    "SHIB",
    "SOL",
    "TRUMP",
    "USDT",
    "WIF",
    "XRP",
}


def normalize_ticker(ticker: str) -> str:
    ticker = ticker.strip().upper().removeprefix("$")
    if ticker in CRYPTO_SUFFIX_CANDIDATES:
        return f"{ticker}-USD"
    return ticker


def normalize_currency(currency: str) -> str:
    currency = currency.strip().upper()
    if currency in {"GBP", "GBX", "GBPENCE", "GB PENCE"}:
        return "GBP"
    return currency


def parse_amount(raw: str) -> Decimal | None:
    try:
        amount = Decimal(raw)
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite() or amount <= 0:
        return None
    return amount


class VTrade:
    def __init__(
        self,
        state: JsonState,
        prices: PriceProvider | None = None,
        fx: FXProvider | None = None,
        now: Callable[[], float] | None = None,
        rng: random.Random | None = None,
        fx_fee: Decimal | str = Decimal("0.005"),
    ):
        self.state = state
        self.prices = prices or YahooPriceProvider()
        self.fx = fx or FXRatesProvider()
        self.now = now or time.time
        self.rng = rng or random.SystemRandom()
        self.fx_fee = Decimal(str(fx_fee))
        data = self.state.data
        data.setdefault("vtrade", {})
        data["vtrade"].setdefault("accounts", {})
        data["vtrade"].setdefault("nick_alias", {})
        data["vtrade"].setdefault("pending", {})

    @property
    def data(self) -> dict:
        return self.state.data["vtrade"]

    def handle(self, nick: str, text: str) -> list[str]:
        args = text.strip().split()
        if len(args) == 1 or (len(args) >= 2 and args[1].lower() == "help"):
            return self.help()

        cmd = args[1].lower()
        if cmd == "claim":
            if len(args) != 3:
                return ["Usage: !vtrade claim <alias>"]
            return self.claim(nick, args[2])
        if cmd in {"buy", "sell"}:
            return self.request_trade(nick, cmd.upper(), args[2:])
        if cmd == "confirm":
            if len(args) != 3:
                return ["Usage: !vtrade confirm <code>"]
            return self.confirm(nick, args[2])
        if cmd == "convert":
            return self.convert(nick, args[2:])
        if cmd == "*":
            return self.leaderboard_graph()
        if cmd in {"top", "leaderboard"}:
            return self.leaderboard()
        return self.portfolio(args[1])

    def help(self) -> list[str]:
        return [
            "--- vTrade Help Menu ---",
            "Welcome to vTrade! A simulated stock trading game. Start with $1000.",
            "",
            "1. Create Account:",
            "   !vtrade claim <alias>  - Claim your initial $1000.",
            "",
            "2. Trading:",
            "   !vtrade buy <ticker> <amount>   - Request to buy stock (e.g., $TSLA). Add",
            "convert to auto-convert USD to the stock's currency if needed.",
            "   !vtrade sell <ticker> <amount>  - Request to sell stock. Add convert to",
            "convert proceeds back to USD for recording.",
            "   * You will receive a 4-digit code to confirm trades.",
            "   !vtrade confirm <code> - Finalize the transaction.",
            "",
            "3. Portfolio:",
            "   !vtrade <alias> - View trading history and performance graph.",
            "   !vtrade help   - Show this menu.",
            "",
            "4. Currency:",
            "   !vtrade convert <from> <to> <amount> - Convert currencies at 0.50% fee.",
            "   You can also use the convert flag when trading foreign stocks to have USD",
            "automatically swapped.",
        ]

    def claim(self, nick: str, alias: str) -> list[str]:
        nick = clean_nick(nick)
        alias = alias.strip()
        if not alias.replace("_", "").replace("-", "").isalnum():
            return ["Alias must contain only letters, numbers, hyphens, or underscores."]
        if alias in self.data["accounts"]:
            return [f"Alias {alias} is already claimed."]
        if nick in self.data["nick_alias"]:
            return [f"{nick} already claimed {self.data['nick_alias'][nick]}."]

        self.data["accounts"][alias] = {
            "alias": alias,
            "owner": nick,
            "cash": {"USD": "1000"},
            "holdings": {},
            "history": [],
        }
        self.data["nick_alias"][nick] = alias
        self.state.save()
        return [f"{alias} claimed. Starting balance: $1,000.00 USD."]

    def request_trade(self, nick: str, side: str, args: list[str]) -> list[str]:
        convert = bool(args and args[-1].lower() == "convert")
        if convert:
            args = args[:-1]
        if len(args) < 2:
            return [f"Usage: !vtrade {side.lower()} <ticker> <quantity>"]
        alias = self.alias_for_nick(nick)
        if alias is None:
            return ["No vTrade account. Use: !vtrade claim <alias>"]

        ticker = normalize_ticker(args[0])
        qty = parse_amount(args[1])
        if qty is None:
            return ["Amount must be a positive number."]

        account = self.data["accounts"][alias]
        try:
            price = self.prices.price(ticker)
        except Exception as exc:
            return [f"Could not fetch price for {ticker}: {exc}"]
        currency = self.currency_for_ticker(ticker)

        total = (price * qty).quantize(Decimal("0.0001"))
        cash = Decimal(account["cash"].get(currency, "0"))
        holdings = account["holdings"]
        convert_from: str | None = None
        convert_to: str | None = None
        convert_rate: Decimal | None = None
        convert_source_total: Decimal | None = None
        convert_fee: Decimal | None = None

        if side == "BUY":
            if currency != "USD" and not convert and total > cash:
                return [
                    f"Foreign Currency Required: {ticker} trades in {currency}. You can append convert or use",
                    f"!vtrade convert USD {currency} <amount> to acquire {currency}.",
                ]
            if convert and currency != "USD":
                try:
                    convert_rate = self.fx.rate("USD", currency)
                except Exception as exc:
                    return [str(exc), f"Error: Could not determine FX rate for USD -> {currency}."]
                convert_from = "USD"
                convert_to = currency
                convert_source_total = (total / (convert_rate * (Decimal("1") - self.fx_fee))).quantize(
                    Decimal("0.0001")
                )
                convert_fee = (convert_source_total * self.fx_fee).quantize(Decimal("0.0001"))
                usd_cash = Decimal(account["cash"].get("USD", "0"))
                if convert_source_total > usd_cash:
                    return [
                        f"Insufficient USD for conversion. Need {compact_money(convert_source_total)} to convert to {quantity(total)} {currency},",
                        f"currently have {compact_money(usd_cash)}.",
                    ]
            elif total > cash:
                return [
                    f"Insufficient Funds. Cost: {compact_money(total)}, Available: {compact_money(cash)}."
                ]
        if side == "SELL":
            held = Decimal(holdings.get(ticker, {}).get("qty", "0"))
            if qty > held:
                return [f"Insufficient Holdings. Have {quantity(held)} {ticker}."]
            if convert and currency != "USD":
                try:
                    convert_rate = self.fx.rate(currency, "USD")
                except Exception as exc:
                    return [str(exc), f"Error: Could not determine FX rate for {currency} -> USD."]
                convert_from = currency
                convert_to = "USD"
                convert_source_total = total
                convert_fee = (total * self.fx_fee).quantize(Decimal("0.0001"))

        pending = PendingTrade(
            nick=clean_nick(nick),
            alias=alias,
            side=side,
            ticker=ticker,
            qty=qty,
            price=price,
            total=total,
            currency=currency,
            expires_at=self.now() + 120,
            convert=convert,
            convert_from=convert_from,
            convert_to=convert_to,
            convert_rate=convert_rate,
            convert_source_total=convert_source_total,
            convert_fee=convert_fee,
        )
        code = self._code()
        self.data["pending"][code] = self._pending_to_json(pending)
        self.state.save()

        lines = [f"{'Verify ' + side + ' Order':^39}"]
        lines.extend(
            table(
                ["Ticker", "Qty", "Price", "Total"],
                [[ticker, quantity(qty), compact_money(price), money(total, currency)]],
                align_right={1, 2, 3},
            )
        )
        lines.append(f"To confirm, type: !vtrade confirm {code} (Expires in 120s)")
        return lines

    def confirm(self, nick: str, code: str) -> list[str]:
        code = code.strip().lower()
        pending_json = self.data["pending"].get(code)
        if not pending_json:
            return ["No pending trade for that code."]
        pending = self._pending_from_json(pending_json)
        if self.now() > pending.expires_at:
            del self.data["pending"][code]
            self.state.save()
            return ["Trade confirmation expired."]
        if clean_nick(nick) != pending.nick:
            return ["That confirmation code belongs to another nick."]

        account = self.data["accounts"][pending.alias]
        currency = pending.currency
        cash = Decimal(account["cash"].get(currency, "0"))
        holdings = account["holdings"]
        holding = holdings.setdefault(pending.ticker, {"qty": "0", "avg_cost": "0"})
        held_qty = Decimal(holding["qty"])
        avg_cost = Decimal(holding["avg_cost"])

        if pending.side == "BUY":
            if pending.convert and pending.convert_source_total is not None:
                source = pending.convert_from or "USD"
                source_cash = Decimal(account["cash"].get(source, "0"))
                if pending.convert_source_total > source_cash:
                    return [
                        f"Insufficient Funds. Cost: {compact_money(pending.convert_source_total)}, Available: {compact_money(source_cash)}."
                    ]
                account["cash"][source] = str(source_cash - pending.convert_source_total)
            else:
                if pending.total > cash:
                    return [
                        f"Insufficient Funds. Cost: {compact_money(pending.total)}, Available: {compact_money(cash)}."
                    ]
                account["cash"][currency] = str(cash - pending.total)
            new_qty = held_qty + pending.qty
            new_avg = ((held_qty * avg_cost) + pending.total) / new_qty
            holding["qty"] = str(new_qty)
            holding["avg_cost"] = str(new_avg)
            holding["currency"] = currency
        else:
            if pending.qty > held_qty:
                return [f"Insufficient Holdings. Have {quantity(held_qty)} {pending.ticker}."]
            new_qty = held_qty - pending.qty
            if pending.convert and pending.convert_rate is not None and pending.convert_fee is not None:
                target = pending.convert_to or "USD"
                target_cash = Decimal(account["cash"].get(target, "0"))
                received = ((pending.total - pending.convert_fee) * pending.convert_rate).quantize(
                    Decimal("0.0001")
                )
                account["cash"][target] = str(target_cash + received)
            else:
                account["cash"][currency] = str(cash + pending.total)
            if new_qty == 0:
                holdings.pop(pending.ticker, None)
            else:
                holding["qty"] = str(new_qty)

        account["history"].append(
            {
                "ts": self.now(),
                "side": pending.side,
                "ticker": pending.ticker,
                "qty": str(pending.qty),
                "price": str(pending.price),
                "total": str(pending.total),
                "currency": currency,
                "net_worth": str(self.account_net_worth(account)),
            }
        )
        del self.data["pending"][code]
        self.state.save()
        return [
            f"Transaction Executed! {pending.side} {quantity(pending.qty)} {pending.ticker} complete."
        ]

    def convert(self, nick: str, args: list[str]) -> list[str]:
        if len(args) != 3:
            return ["Usage: !vtrade convert <from> <to> <amount>"]
        alias = self.alias_for_nick(nick)
        if alias is None:
            return ["No vTrade account. Use: !vtrade claim <alias>"]
        from_currency = normalize_currency(args[0])
        to_currency = normalize_currency(args[1])
        amount = parse_amount(args[2])
        if amount is None:
            return ["Amount must be a positive number."]
        account = self.data["accounts"][alias]
        cash = Decimal(account["cash"].get(from_currency, "0"))
        if amount > cash:
            return [
                f"Insufficient {from_currency}. Have {money(cash, from_currency)}, need {money(amount, from_currency)}."
            ]
        try:
            rate = self.fx.rate(from_currency, to_currency)
        except Exception as exc:
            return [str(exc), f"Error: Could not determine FX rate for {from_currency} -> {to_currency}."]
        fee = (amount * self.fx_fee).quantize(Decimal("0.0001"))
        received = ((amount - fee) * rate).quantize(Decimal("0.0001"))
        account["cash"][from_currency] = str(cash - amount)
        account["cash"][to_currency] = str(Decimal(account["cash"].get(to_currency, "0")) + received)
        self.state.save()
        return [
            f"Conversion Complete! {money(amount, from_currency)} -> {quantity(received)} {to_currency} at {rate} (fee {money(fee, from_currency)})."
        ]

    def portfolio(self, alias: str) -> list[str]:
        account = self.data["accounts"].get(alias)
        if not account:
            return [f"No portfolio for {alias}."]
        cash_accounts = account.get("cash", {})
        lines = [f"Portfolio for {alias}", ""]
        for currency, amount in sorted(cash_accounts.items()):
            amount_dec = Decimal(amount)
            if amount_dec:
                lines.append(f"   {currency}: {compact_money(amount_dec)}")
        if len(lines) == 2:
            lines.append("   USD: $0.00")
        lines.append("")
        holdings = account.get("holdings", {})
        if not holdings:
            lines.append("No active stock holdings.")
            return lines

        rows: list[list[str]] = []
        net = self.cash_value_usd(cash_accounts)
        cost_total = Decimal("1000")
        for ticker, holding in sorted(holdings.items()):
            qty = Decimal(holding["qty"])
            avg = Decimal(holding["avg_cost"])
            currency = normalize_currency(holding.get("currency") or self.currency_for_ticker(ticker))
            try:
                price = self.prices.price(ticker)
            except Exception:
                price = avg
            value = qty * price
            pl = value - (qty * avg)
            pct = Decimal("0") if avg == 0 else (price - avg) / avg * Decimal("100")
            net += self.to_usd(value, currency)
            rows.append(
                [
                    ticker,
                    quantity(qty),
                    compact_money(avg),
                    compact_money(price),
                    compact_money(value),
                    money(pl, currency),
                    f"{pct:+.2f}%",
                ]
            )

        lines.extend(
            [
                "  Ticker        Qty   Avg Cost   Price        Value      P/L ($)   P/L (%)",
                " " + "─" * 74,
            ]
        )
        for row in rows:
            lines.append(
                f"  {row[0]:<10} {row[1]:>8} {row[2]:>10} {row[3]:>8} {row[4]:>12} {row[5]:>12} {row[6]:>9}"
            )
        pct = (net - cost_total) / cost_total * Decimal("100")
        lines.extend(["", f"Total Net Worth: {compact_money(net)} ({pct:+.2f}%)"])
        return lines

    def leaderboard(self) -> list[str]:
        rows = []
        for alias, account in self.data["accounts"].items():
            net = self.account_net_worth(account)
            rows.append((net, alias))
        if not rows:
            return ["No vTrade portfolios yet."]
        rows.sort(reverse=True)
        out = ["vTrade leaderboard"]
        medals = ["🥇", "🥈", "🥉"]
        for idx, (net, alias) in enumerate(rows[:10], start=1):
            prefix = medals[idx - 1] if idx <= 3 else f"{idx}."
            delta = net - Decimal("1000")
            out.append(f"{prefix} {alias} ({money(delta)}) - net worth {compact_money(net)}")
        return out

    def leaderboard_graph(self) -> list[str]:
        rows = [
            (self.account_net_worth(account), alias, account)
            for alias, account in self.data["accounts"].items()
        ]
        if not rows:
            return ["No vTrade portfolios yet."]
        rows.sort(reverse=True, key=lambda item: item[0])
        medals = ["🥇", "🥈", "🥉"]
        out: list[str] = []
        for idx, (net, alias, account) in enumerate(rows[:10], start=1):
            prefix = medals[idx - 1] if idx <= 3 else f"{idx}."
            delta = net - Decimal("1000")
            values = self.net_worth_history(account, net)
            out.append(f"{prefix} {alias} ({money(delta)})")
            out.extend(render_value_graph(values, alias))
            out.append("------------------------------------------------------------")
        return out

    def alias_for_nick(self, nick: str) -> str | None:
        return self.data["nick_alias"].get(clean_nick(nick))

    def currency_for_ticker(self, ticker: str) -> str:
        currency = getattr(self.prices, "currency", None)
        if callable(currency):
            try:
                return normalize_currency(currency(ticker))
            except Exception:
                return "USD"
        return "USD"

    def cash_value_usd(self, cash: dict[str, str]) -> Decimal:
        total = Decimal(cash.get("USD", "0"))
        for currency, amount in cash.items():
            currency = normalize_currency(currency)
            if currency == "USD":
                continue
            total += self.to_usd(Decimal(amount), currency)
        return total

    def to_usd(self, amount: Decimal, currency: str) -> Decimal:
        currency = normalize_currency(currency)
        if currency == "USD":
            return amount
        try:
            return amount * self.fx.rate(currency, "USD")
        except Exception:
            return Decimal("0")

    def account_net_worth(self, account: dict) -> Decimal:
        net = self.cash_value_usd(account.get("cash", {}))
        for ticker, holding in account.get("holdings", {}).items():
            qty = Decimal(holding["qty"])
            currency = normalize_currency(holding.get("currency") or self.currency_for_ticker(ticker))
            try:
                price = self.prices.price(ticker)
            except Exception:
                price = Decimal(holding["avg_cost"])
            net += self.to_usd(qty * price, currency)
        return net

    @staticmethod
    def net_worth_history(account: dict, current_net: Decimal) -> list[Decimal]:
        values = [Decimal("1000")]
        for item in account.get("history", []):
            raw = item.get("net_worth")
            if raw is not None:
                values.append(Decimal(str(raw)))
        if values[-1] != current_net:
            values.append(current_net)
        return values[-28:]

    def _code(self) -> str:
        alphabet = string.ascii_lowercase + string.digits
        while True:
            code = "".join(self.rng.choice(alphabet) for _ in range(4))
            if code not in self.data["pending"]:
                return code

    @staticmethod
    def _pending_to_json(pending: PendingTrade) -> dict[str, str | float]:
        return {
            "nick": pending.nick,
            "alias": pending.alias,
            "side": pending.side,
            "ticker": pending.ticker,
            "qty": str(pending.qty),
            "price": str(pending.price),
            "total": str(pending.total),
            "currency": pending.currency,
            "expires_at": pending.expires_at,
            "convert": pending.convert,
            "convert_from": pending.convert_from,
            "convert_to": pending.convert_to,
            "convert_rate": None if pending.convert_rate is None else str(pending.convert_rate),
            "convert_source_total": None
            if pending.convert_source_total is None
            else str(pending.convert_source_total),
            "convert_fee": None if pending.convert_fee is None else str(pending.convert_fee),
        }

    @staticmethod
    def _pending_from_json(raw: dict) -> PendingTrade:
        return PendingTrade(
            nick=raw["nick"],
            alias=raw["alias"],
            side=raw["side"],
            ticker=raw["ticker"],
            qty=Decimal(raw["qty"]),
            price=Decimal(raw["price"]),
            total=Decimal(raw["total"]),
            currency=normalize_currency(raw.get("currency", "USD")),
            expires_at=float(raw["expires_at"]),
            convert=bool(raw.get("convert", False)),
            convert_from=raw.get("convert_from"),
            convert_to=raw.get("convert_to"),
            convert_rate=None if raw.get("convert_rate") is None else Decimal(raw["convert_rate"]),
            convert_source_total=None
            if raw.get("convert_source_total") is None
            else Decimal(raw["convert_source_total"]),
            convert_fee=None if raw.get("convert_fee") is None else Decimal(raw["convert_fee"]),
        )


def render_value_graph(values: list[Decimal], label: str, width: int = 24) -> list[str]:
    if not values:
        values = [Decimal("1000")]
    samples = resample_values(values, width)
    low = min(samples)
    high = max(samples)
    graph = sparkline(samples)
    if high == low:
        mid = high
    else:
        mid = (high + low) / 2
    pct = Decimal("0") if values[0] == 0 else (values[-1] - values[0]) / values[0] * Decimal("100")
    return [
        "                              ╷",
        f"  {compact_money(high):>8} {graph} │  {label}  {pct:+.1f}%  {money(values[-1] - values[0])}",
        f"  {compact_money(mid):>8} {graph} │",
        f"  {compact_money(low):>8} {graph} │",
        "  --------------------------- │",
        "                              ╵",
        f"Δ all: {pct:+.2f}%",
    ]


def resample_values(values: list[Decimal], width: int) -> list[Decimal]:
    if len(values) >= width:
        return [values[round(index * (len(values) - 1) / (width - 1))] for index in range(width)]
    return values + [values[-1]] * (width - len(values))


def sparkline(values: list[Decimal]) -> str:
    blocks = "▁▂▃▄▅▆▇█"
    low = min(values)
    high = max(values)
    if high == low:
        return blocks[0] * len(values)
    span = high - low
    chars = []
    for value in values:
        index = int(((value - low) / span * (len(blocks) - 1)).to_integral_value())
        index = max(0, min(len(blocks) - 1, index))
        chars.append(blocks[index])
    return "".join(chars)
