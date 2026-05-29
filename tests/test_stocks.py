from __future__ import annotations

from decimal import Decimal
import unittest

from pyylmao.stocks import StockPoint, parse_stock_options, render_stock_command


class StaticHistoryProvider:
    def __init__(self, values: list[str]):
        self.values = values
        self.calls: list[tuple[str, str]] = []

    def history(self, ticker: str, period: str) -> list[StockPoint]:
        self.calls.append((ticker, period))
        return [
            StockPoint(timestamp=1_700_000_000 + index * 86_400, close=Decimal(value))
            for index, value in enumerate(self.values)
        ]


class StockTests(unittest.TestCase):
    def test_default_stock_chart_shape(self) -> None:
        provider = StaticHistoryProvider(["100", "102", "101", "110", "108", "115"])
        lines = render_stock_command("!stock TSLA", provider)
        self.assertEqual(provider.calls, [("TSLA", "30d")])
        self.assertEqual(lines[0], "Trading Prices for TSLA (Past 30 Days):")
        self.assertEqual(lines[1], "Price range: $100.00 - $115.00")
        self.assertEqual(lines[2], "")
        self.assertEqual(len(lines[3:11]), 8)
        self.assertEqual(lines[11], "-" * 38)
        self.assertTrue(lines[12].startswith("        "))

    def test_wide_numeric_arg_matches_all_time_log_style(self) -> None:
        provider = StaticHistoryProvider(["1", "2", "3"])
        lines = render_stock_command("!stock COHR 90", provider)
        self.assertEqual(provider.calls, [("COHR", "max")])
        self.assertEqual(lines[0], "Trading Prices for COHR (All Time):")
        self.assertEqual(len(lines[3][8:]), 90)

    def test_parse_short_numeric_arg_as_days(self) -> None:
        options = parse_stock_options("14")
        self.assertEqual(options.period, "14d")
        self.assertEqual(options.label, "Past 14 Days")


if __name__ == "__main__":
    unittest.main()
