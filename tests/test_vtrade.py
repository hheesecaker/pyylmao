from __future__ import annotations

import random
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from pyylmao.state import JsonState
from pyylmao.vtrade import (
    StaticFXProvider,
    StaticPriceProvider,
    VTrade,
    normalize_ticker,
    parse_amount,
    sparkline,
)


class VTradeTests(unittest.TestCase):
    def make_bot(self) -> VTrade:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = JsonState(Path(tmp.name) / "state.json")
        prices = StaticPriceProvider(
            {"TSLA": "250", "XRP-USD": "2", "AZN.L": "100"},
            currencies={"AZN.L": "GBP"},
        )
        fx = StaticFXProvider({("USD", "GBP"): "0.5"})
        return VTrade(state, prices=prices, fx=fx, now=lambda: 1000.0, rng=random.Random(1))

    def test_claim_buy_confirm_and_portfolio(self) -> None:
        bot = self.make_bot()
        self.assertEqual(bot.handle("alice", "!vtrade claim alice"), ["alice claimed. Starting balance: $1,000.00 USD."])

        request = bot.handle("alice", "!vtrade buy TSLA 2")
        self.assertIn("Verify BUY Order", request[0])
        confirm_line = request[-1]
        code = confirm_line.split("confirm ", 1)[1].split()[0]

        self.assertEqual(
            bot.handle("alice", f"!vtrade confirm {code}"),
            ["Transaction Executed! BUY 2 TSLA complete."],
        )
        portfolio = "\n".join(bot.handle("alice", "!vtrade alice"))
        self.assertIn("Portfolio for alice", portfolio)
        self.assertIn("TSLA", portfolio)
        self.assertIn("Total Net Worth: $1,000.00", portfolio)

    def test_rejects_invalid_and_insufficient_buy(self) -> None:
        bot = self.make_bot()
        bot.handle("alice", "!vtrade claim alice")
        self.assertEqual(bot.handle("alice", "!vtrade buy TSLA nope"), ["Amount must be a positive number."])
        self.assertEqual(
            bot.handle("alice", "!vtrade buy TSLA 999"),
            ["Insufficient Funds. Cost: $249,750.00, Available: $1,000.00."],
        )

    def test_sell_requires_holdings(self) -> None:
        bot = self.make_bot()
        bot.handle("alice", "!vtrade claim alice")
        self.assertEqual(
            bot.handle("alice", "!vtrade sell TSLA 1"),
            ["Insufficient Holdings. Have 0 TSLA."],
        )

    def test_crypto_ticker_normalization_and_amount_validation(self) -> None:
        self.assertEqual(normalize_ticker("btc"), "BTC-USD")
        self.assertEqual(normalize_ticker("$tsla"), "TSLA")
        self.assertEqual(parse_amount("0.1"), Decimal("0.1"))
        self.assertIsNone(parse_amount("-1"))
        self.assertIsNone(parse_amount("nan"))

    def test_currency_conversion_charges_half_percent_fee(self) -> None:
        bot = self.make_bot()
        bot.handle("alice", "!vtrade claim alice")
        self.assertEqual(
            bot.handle("alice", "!vtrade convert USD GBP 100"),
            ["Conversion Complete! $100.00 USD -> 49.75 GBP at 0.5 (fee $0.50 USD)."],
        )
        portfolio = "\n".join(bot.handle("alice", "!vtrade alice"))
        self.assertIn("USD: $900.00", portfolio)
        self.assertIn("GBP: $49.75", portfolio)

    def test_foreign_stock_requires_currency_or_convert_flag(self) -> None:
        bot = self.make_bot()
        bot.handle("alice", "!vtrade claim alice")
        self.assertEqual(
            bot.handle("alice", "!vtrade buy AZN.L 1"),
            [
                "Foreign Currency Required: AZN.L trades in GBP. You can append convert or use",
                "!vtrade convert USD GBP <amount> to acquire GBP.",
            ],
        )

        request = bot.handle("alice", "!vtrade buy AZN.L 1 convert")
        self.assertIn("Verify BUY Order", request[0])
        code = request[-1].split("confirm ", 1)[1].split()[0]
        self.assertEqual(
            bot.handle("alice", f"!vtrade confirm {code}"),
            ["Transaction Executed! BUY 1 AZN.L complete."],
        )
        portfolio = "\n".join(bot.handle("alice", "!vtrade alice"))
        self.assertIn("AZN.L", portfolio)
        self.assertIn("Total Net Worth: $999.00", portfolio)

    def test_star_leaderboard_includes_graph(self) -> None:
        bot = self.make_bot()
        bot.handle("alice", "!vtrade claim alice")
        request = bot.handle("alice", "!vtrade buy TSLA 1")
        code = request[-1].split("confirm ", 1)[1].split()[0]
        bot.handle("alice", f"!vtrade confirm {code}")
        board = "\n".join(bot.handle("alice", "!vtrade *"))
        self.assertIn("🥇 alice", board)
        self.assertIn("Δ all:", board)
        self.assertIn("---------------------------", board)

    def test_sparkline_scales_values(self) -> None:
        self.assertEqual(sparkline([Decimal("1"), Decimal("2"), Decimal("3")]), "▁▅█")


if __name__ == "__main__":
    unittest.main()
