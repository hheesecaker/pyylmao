from __future__ import annotations

import unittest

from pyylmao.livebench import (
    SIMPLE_COLUMNS,
    LiveBenchDataset,
    LiveBenchError,
    LiveBenchRow,
    is_livebench_command,
    parse_livebench_command,
    parse_livebench_dataset,
    render_livebench_command,
)


class FakeProvider:
    def __init__(self, dataset: LiveBenchDataset | None = None, error: Exception | None = None):
        self.dataset = dataset or fake_dataset()
        self.error = error

    def load(self) -> LiveBenchDataset:
        if self.error is not None:
            raise self.error
        return self.dataset


def fake_dataset() -> LiveBenchDataset:
    categories = {
        "reasoning": ("theory_of_mind", "zebra_puzzle"),
        "coding": ("code_generation", "code_completion"),
        "agentic_coding": ("javascript", "typescript", "python"),
        "mathematics": ("amps_hard", "math_comp"),
        "data_analysis": ("tablejoin", "tablereformat"),
        "language": ("connections", "typos"),
        "if": ("paraphrase", "summarize"),
    }
    return LiveBenchDataset(
        date="2026-01-08",
        source_url="https://livebench.ai/table_2026_01_08.csv",
        categories=categories,
        rows=(
            LiveBenchRow(
                model="alpha-model",
                scores={
                    "theory_of_mind": 80.0,
                    "zebra_puzzle": 70.0,
                    "code_generation": 80.0,
                    "code_completion": 90.0,
                    "javascript": 50.0,
                    "typescript": 70.0,
                    "python": 90.0,
                    "amps_hard": 95.0,
                    "math_comp": 85.0,
                    "tablejoin": 60.0,
                    "tablereformat": 80.0,
                    "connections": 70.0,
                    "typos": 90.0,
                    "paraphrase": 50.0,
                    "summarize": 70.0,
                },
            ),
            LiveBenchRow(
                model="beta-model",
                scores={
                    "theory_of_mind": 60.0,
                    "zebra_puzzle": 60.0,
                    "code_generation": 50.0,
                    "code_completion": 70.0,
                    "javascript": 100.0,
                    "typescript": 100.0,
                    "python": 100.0,
                    "amps_hard": 60.0,
                    "math_comp": 60.0,
                    "tablejoin": 40.0,
                    "tablereformat": 60.0,
                    "connections": 60.0,
                    "typos": 60.0,
                    "paraphrase": 80.0,
                    "summarize": 100.0,
                },
            ),
        ),
    )


class LiveBenchTests(unittest.TestCase):
    def test_command_detection_matches_logged_pattern(self) -> None:
        self.assertTrue(is_livebench_command("!livebench"))
        self.assertTrue(is_livebench_command("?livebench +simple"))
        self.assertFalse(is_livebench_command("!livebenchx +simple"))

    def test_parse_simple_and_category_filters(self) -> None:
        request = parse_livebench_command("!livebench -top 8 +simple language")
        self.assertIsNotNone(request)
        assert request is not None
        self.assertTrue(request.simple)
        self.assertEqual(request.top, 8)
        self.assertEqual(request.columns, ("language",))

        request = parse_livebench_command("!livebench +simple coding,agentic_coding,reasoning")
        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.columns, ("coding", "agentic_coding", "reasoning"))

        request = parse_livebench_command("!livebench +simple")
        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.columns, SIMPLE_COLUMNS)

    def test_parse_sort_option(self) -> None:
        request = parse_livebench_command("!livebench +simple -sort coding asc")
        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.sort_by, "coding")
        self.assertFalse(request.sort_desc)
        self.assertEqual(request.columns, SIMPLE_COLUMNS)

    def test_simple_table_uses_recent_logged_separator_style(self) -> None:
        lines = render_livebench_command("!livebench +simple", provider=FakeProvider())
        self.assertEqual(lines[0], "")
        self.assertIn("MODEL", lines[2])
        self.assertIn("🭍", lines[2])
        self.assertIn("alpha-model", lines[3])
        self.assertIn("75.71", lines[3])
        self.assertTrue(lines[-3].startswith("🮝"))

    def test_top_and_category_filters_sort_by_requested_average(self) -> None:
        lines = render_livebench_command(
            "!livebench -top 1 +simple coding,agentic_coding",
            provider=FakeProvider(),
        )
        table = "\n".join(lines)
        self.assertIn("CODING", lines[2])
        self.assertIn("AGENTIC_CODING", lines[2])
        self.assertIn("AVG", lines[2])
        self.assertIn("beta-model", table)
        self.assertIn("80.0", table)
        self.assertEqual(sum(1 for line in lines if "🭍" in line and "MODEL" not in line), 1)

    def test_sort_option_orders_by_requested_column_without_changing_displayed_columns(self) -> None:
        lines = render_livebench_command(
            "!livebench -top 1 +simple -sort coding agentic_coding",
            provider=FakeProvider(),
        )
        self.assertIn("AGENTIC_CODING", lines[2])
        self.assertNotIn("REASONING", lines[2])
        self.assertIn("alpha-model", "\n".join(lines))

        lines = render_livebench_command(
            "!livebench -top 1 +simple -sort coding asc agentic_coding",
            provider=FakeProvider(),
        )
        self.assertIn("beta-model", "\n".join(lines))

    def test_bare_livebench_renders_full_plain_pipe_table(self) -> None:
        lines = render_livebench_command("!livebench", provider=FakeProvider())
        self.assertTrue(lines[0].startswith(" | MODEL"))
        self.assertIn("AMPS_HARD", lines[0])
        self.assertIn("alpha-model", lines[1])

    def test_parse_online_csv_and_categories_schema(self) -> None:
        dataset = parse_livebench_dataset(
            "2026-01-08",
            "https://livebench.ai/table_2026_01_08.csv",
            "model,AMPS_Hard,code_generation\nmodel-a,61.0,70.423\n",
            '{"Mathematics": ["AMPS_Hard"], "Coding": ["code_generation"]}',
        )
        self.assertEqual(dataset.date, "2026-01-08")
        self.assertEqual(dataset.categories["mathematics"], ("amps_hard",))
        self.assertEqual(dataset.rows[0].scores["code_generation"], 70.423)

    def test_fetch_failures_are_reported(self) -> None:
        lines = render_livebench_command(
            "!livebench +simple",
            provider=FakeProvider(error=LiveBenchError("offline")),
        )
        self.assertEqual(lines, ["LiveBench fetch failed: offline"])


if __name__ == "__main__":
    unittest.main()
