from __future__ import annotations

import unittest

from pyylmao.huggingface import HFModel, render_hf_command


class StaticHFProvider:
    def trending(self, limit: int = 10) -> list[HFModel]:
        self.limit = limit
        return [
            HFModel("nvidia/personaplex-7b-v1", "2026-01-28T12:00:00.000Z"),
            HFModel("moonshotai/Kimi-K2.5", "2026-01-29T00:01:02.000Z"),
        ]


class HuggingFaceTests(unittest.TestCase):
    def test_hf_trending_format_matches_logs(self) -> None:
        provider = StaticHFProvider()
        self.assertEqual(
            render_hf_command("!hf", provider),
            [
                "HF Trending (Last 1 Days):",
                " ★ 2026-01-28  nvidia/personaplex-7b-v1  https://huggingface.co/nvidia/personaplex-7b-v1",
                " ★ 2026-01-29  moonshotai/Kimi-K2.5      https://huggingface.co/moonshotai/Kimi-K2.5",
            ],
        )
        self.assertEqual(provider.limit, 10)

    def test_hf_usage(self) -> None:
        self.assertEqual(render_hf_command("!hf now", StaticHFProvider()), ["Usage: !hf"])


if __name__ == "__main__":
    unittest.main()
