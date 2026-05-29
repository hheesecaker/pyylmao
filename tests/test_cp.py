from __future__ import annotations

import unittest

from pyylmao.cp import parse_tickers, render_cp_command


class CryptoPriceCommandTests(unittest.TestCase):
    def test_parse_tickers_preserves_order_and_dedupes(self) -> None:
        self.assertEqual(parse_tickers("btc, eth BTC sol"), ["btc", "eth", "sol"])

    def test_render_cp_command_uses_md2irc_table_shape(self) -> None:
        lines = render_cp_command(
            "tcl cp btc eth",
            fetcher=lambda tickers: {"btc": 78427, "eth": 2310.21},
        )

        self.assertIn(" Ticker 🭍  Price (USD) 🭍", lines)
        self.assertIn(" BTC    🭍  $78,427.00  🭍", lines)
        self.assertIn(" ETH    🭍  $2,310.21   🭍", lines)

    def test_render_cp_command_lists_unknown_tickers(self) -> None:
        self.assertEqual(
            render_cp_command("tcl cp nope", fetcher=lambda tickers: {}),
            ["Unknown tickers: NOPE"],
        )
        lines = render_cp_command(
            "tcl cp btc nope",
            fetcher=lambda tickers: {"btc": 1},
        )
        self.assertEqual(lines[-1], "Unknown tickers: NOPE")


if __name__ == "__main__":
    unittest.main()
