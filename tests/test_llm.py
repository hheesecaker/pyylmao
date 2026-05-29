from __future__ import annotations

import unittest
from decimal import Decimal

from pyylmao.llm import LLMResult, OpenRouterClient, format_cents, format_model_name, stats_line, tool_result_trace


class LLMFormattingTests(unittest.TestCase):
    def test_model_name_uses_current_logged_openrouter_style(self) -> None:
        self.assertEqual(format_model_name("tencent/hy3-preview"), "𝚝𝚎𝚗𝚌𝚎𝚗𝚝/𝚑𝚢𝟹-𝚙𝚛𝚎𝚟𝚒𝚎𝚠")
        self.assertEqual(format_model_name("x-ai/grok-4.3"), "𝚡-𝚊𝚒/𝚐𝚛𝚘𝚔-𝟺.𝟹")
        self.assertEqual(format_model_name("openai/gpt-oss-120b"), "𝚘𝚙𝚎𝚗𝚊𝚒/𝚐𝚙𝚝-𝚘𝚜𝚜-𝟷𝟸0𝚋")

    def test_format_cents_matches_logged_precision(self) -> None:
        self.assertEqual(format_cents(Decimal("0.00004")), "0.004")
        self.assertEqual(format_cents(Decimal("0.0005")), "0.05")
        self.assertEqual(format_cents(Decimal("0.213")), "21.3")
        self.assertEqual(format_cents(Decimal("0.25")), "25")

    def test_stats_line_matches_single_request_shape(self) -> None:
        result = LLMResult(
            ["ok"],
            17.6,
            576,
            239,
            "tencent/hy3-preview",
            cost_usd=Decimal("0.0001"),
            total_cost_usd=Decimal("0.0249"),
        )

        self.assertEqual(
            stats_line(result),
            "\x039417.6 \x0393𝘴𝘦𝘤 ‖ "
            "\x0394576 \x0393🢃 ‖ "
            "\x0394239 \x0393🡹 ‖ "
            "\x03940.01¢ \x0393━ ‖ "
            "\x03942.49¢ \x0393㍰ ‖ "
            "\x0394𝚝𝚎𝚗𝚌𝚎𝚗𝚝/𝚑𝚢𝟹-𝚙𝚛𝚎𝚟𝚒𝚎𝚠 \x0393𝚘𝚙𝚎𝚗𝚛𝚘𝚞𝚝𝚎𝚛",
        )

    def test_stats_line_matches_multi_request_shape(self) -> None:
        result = LLMResult(
            ["ok"],
            9.8,
            8782,
            505,
            "openai/gpt-oss-120b",
            request_count=2,
            cost_usd=Decimal("0.0005"),
            total_cost_usd=Decimal("0.0321"),
        )

        self.assertEqual(
            stats_line(result),
            "\x03942 \x0393𝘳𝘦𝘲 ‖ "
            "\x03949.8 \x0393𝘴𝘦𝘤 ‖ "
            "\x03948782 \x0393🢃 ‖ "
            "\x0394505 \x0393🡹 ‖ "
            "\x03940.05¢ \x0393━ ‖ "
            "\x03943.21¢ \x0393㍰ ‖ "
            "\x0394𝚘𝚙𝚎𝚗𝚊𝚒/𝚐𝚙𝚝-𝚘𝚜𝚜-𝟷𝟸0𝚋 \x0393𝚘𝚙𝚎𝚗𝚛𝚘𝚞𝚝𝚎𝚛",
        )

    def test_semantic_search_tool_trace_shows_profile_only(self) -> None:
        self.assertEqual(
            tool_result_trace("semantic_search", "Profile: balanced\nQuery: caffeine vape"),
            "Profile: balanced",
        )


class OpenRouterClientStatsTests(unittest.TestCase):
    def test_chat_applies_logged_prompt_options_to_payload(self) -> None:
        calls = []

        def transport(payload):
            calls.append(payload)
            return {
                "model": "test/model",
                "usage": {"prompt_tokens": 1, "completion_tokens": 2},
                "choices": [{"message": {"role": "assistant", "content": "done"}}],
            }

        client = OpenRouterClient("test-key", transport=transport)
        result = client.chat(
            "hello",
            "test/model",
            temperature=1.5,
            extra_system="You are terse",
        )

        self.assertEqual(result.lines, ["done"])
        self.assertEqual(calls[0]["temperature"], 1.5)
        self.assertIn("You are pyylmao", calls[0]["messages"][0]["content"])
        self.assertIn(
            "User system prompt:\nYou are terse",
            calls[0]["messages"][0]["content"],
        )

    def test_chat_builds_image_attachment_payload(self) -> None:
        calls = []

        class Attachment:
            type = "image/png"
            url = "https://example.test/a.png"

        def transport(payload):
            calls.append(payload)
            return {
                "model": "test/model",
                "usage": {"prompt_tokens": 1, "completion_tokens": 2},
                "choices": [{"message": {"role": "assistant", "content": "done"}}],
            }

        client = OpenRouterClient("test-key", transport=transport)
        result = client.chat("describe", "test/model", attachments=[Attachment()])

        self.assertEqual(result.lines, ["done"])
        self.assertEqual(
            calls[0]["messages"][1]["content"],
            [
                {"type": "text", "text": "describe"},
                {"type": "image_url", "image_url": {"url": "https://example.test/a.png"}},
            ],
        )

    def test_accumulates_response_cost_and_request_count(self) -> None:
        calls = []

        def transport(payload):
            calls.append(payload)
            return {
                "model": "test/model",
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                    "cost": "0.0001234",
                },
                "choices": [{"message": {"role": "assistant", "content": "done"}}],
            }

        client = OpenRouterClient("test-key", transport=transport)
        first = client.chat("hello", "test/model")
        second = client.chat("hello again", "test/model")

        self.assertEqual(len(calls), 2)
        self.assertEqual(first.request_count, 1)
        self.assertEqual(first.cost_usd, Decimal("0.0001234"))
        self.assertEqual(first.total_cost_usd, Decimal("0.0001234"))
        self.assertEqual(second.cost_usd, Decimal("0.0001234"))
        self.assertEqual(second.total_cost_usd, Decimal("0.0002468"))


if __name__ == "__main__":
    unittest.main()
