from __future__ import annotations

import unittest
from decimal import Decimal

from pyylmao.llm_prices import (
    LLMPriceRow,
    bold_italic,
    format_dollars,
    is_llm_prices_command,
    parse_model_query,
    render_llm_prices_command,
    render_price_table,
    rows_from_openrouter,
)


class FakeProvider:
    def __init__(self, models: list[dict]):
        self._models = models

    def models(self) -> list[dict]:
        return self._models


class LLMPricesTests(unittest.TestCase):
    def test_command_detection_and_query_parsing(self) -> None:
        self.assertTrue(is_llm_prices_command("$llm gpt-5"))
        self.assertTrue(is_llm_prices_command("  $LLM kimi k2  "))
        self.assertFalse(is_llm_prices_command("$llm"))
        self.assertFalse(is_llm_prices_command("!llm gpt-5"))
        self.assertEqual(parse_model_query("$llm kimi k2"), "k2")
        self.assertEqual(parse_model_query("$llm 'GLM-4.7'"), "glm-4.7")

    def test_static_price_table_matches_logged_shape(self) -> None:
        lines = render_llm_prices_command("$llm gpt-3.5-turbo")
        self.assertEqual(lines[0], "𝒍𝒍𝒎-𝒑𝒓𝒊𝒄𝒆𝒔 𝒇𝒐𝒓 '𝒈𝒑𝒕-3.5-𝒕𝒖𝒓𝒃𝒐'")
        self.assertEqual(lines[1], "")
        self.assertIn(" Provider   | In $/MTok | Out $/MTok ", lines)
        self.assertIn(" azure      | $1.5      | $2         ", lines)
        self.assertIn(" openai     | $0.5      | $1.5       ", lines)
        self.assertIn(" openrouter | $0.5      | $1.5       ", lines)
        self.assertEqual(lines[-2:], ["", ""])

    def test_cache_columns_are_added_when_present(self) -> None:
        lines = render_price_table(
            [LLMPriceRow("anthropic", Decimal("1"), Decimal("5"), Decimal("0.1"), Decimal("1.25"))]
        )
        self.assertEqual(
            lines,
            [
                " Provider  | In $/MTok | Out $/MTok | Cache Read $/MTok | Cache Write $/MTok ",
                " anthropic | $1        | $5         | $0.1              | $1.25              ",
            ],
        )

    def test_openrouter_exact_suffix_match(self) -> None:
        models = [
            {
                "id": "nvidia/nemotron-nano-9b-v2",
                "canonical_slug": "nvidia/nemotron-nano-9b-v2",
                "name": "Nemotron Nano 9B V2",
                "pricing": {
                    "prompt": "0.0000002",
                    "completion": "0.0000005",
                    "input_cache_read": "0.00000005",
                },
            }
        ]
        self.assertEqual(
            rows_from_openrouter("nemotron-nano-9b-v2", models),
            [LLMPriceRow("openrouter/nvidia", Decimal("0.2000000"), Decimal("0.5000000"), Decimal("0.05000000"))],
        )

        lines = render_llm_prices_command(
            "$llm nemotron-nano-9b-v2",
            provider=FakeProvider(models),
        )
        self.assertEqual(lines[0], "Fetching OpenRouter model data...")
        self.assertEqual(lines[1], "𝒍𝒍𝒎-𝒑𝒓𝒊𝒄𝒆𝒔 𝒇𝒐𝒓 '𝒏𝒆𝒎𝒐𝒕𝒓𝒐𝒏-𝒏𝒂𝒏𝒐-9𝒃-𝒗2'")
        self.assertIn(" openrouter/nvidia | $0.2      | $0.5       | $0.05             ", lines)

    def test_no_match_uses_last_query_token_like_logs(self) -> None:
        self.assertEqual(
            render_llm_prices_command("$llm kimi k2", provider=FakeProvider([])),
            ["Fetching OpenRouter model data...", "no matches for model 'k2'"],
        )

    def test_format_helpers(self) -> None:
        self.assertEqual(format_dollars(Decimal("1.250000")), "$1.25")
        self.assertEqual(format_dollars(Decimal("0.050000")), "$0.05")
        self.assertEqual(bold_italic("llm-prices"), "𝒍𝒍𝒎-𝒑𝒓𝒊𝒄𝒆𝒔")


if __name__ == "__main__":
    unittest.main()
