from __future__ import annotations

import unittest

from pyylmao.urbandict import (
    IRC_BOLD,
    SEPARATOR,
    UrbanEntry,
    is_urban_command,
    parse_urban_term,
    render_urban_command,
)


class StaticUrbanProvider:
    def __init__(self, entries: list[UrbanEntry]):
        self.entries = entries
        self.calls: list[tuple[str, int]] = []

    def define(self, term: str, limit: int = 3) -> list[UrbanEntry]:
        self.calls.append((term, limit))
        return self.entries[:limit]


class UrbanDictTests(unittest.TestCase):
    def test_detects_ud_and_urban_commands(self) -> None:
        self.assertTrue(is_urban_command("!ud strong"))
        self.assertTrue(is_urban_command("!urban da bomb"))
        self.assertFalse(is_urban_command("!urbandict strong"))

    def test_parses_term(self) -> None:
        self.assertEqual(parse_urban_term("!ud  strong "), "strong")
        self.assertEqual(parse_urban_term("!urban da bomb"), "da bomb")
        self.assertIsNone(parse_urban_term("!urban"))

    def test_renders_recent_logged_definition_shape(self) -> None:
        provider = StaticUrbanProvider(
            [
                UrbanEntry(
                    word="strong",
                    definition=(
                        "someone who comes off as confident\n"
                        "someone who is comfortable in there own skin"
                    ),
                    example="Erin is a very strong person.",
                ),
                UrbanEntry(
                    word="strong",
                    definition="very potent weed",
                    example='"hey bruh put that away"',
                ),
            ]
        )

        self.assertEqual(
            render_urban_command("!urban strong", provider),
            [
                "Definitions for 𝚂𝚃𝚁𝙾𝙽𝙶",
                SEPARATOR,
                "someone who comes off as confident",
                "someone who is comfortable in there own skin",
                "\xa0",
                "┃ Erin is a very strong person.",
                "\xa0",
                "very potent weed",
                "\xa0",
                '┃ "hey bruh put that away"',
                "",
            ],
        )
        self.assertEqual(provider.calls, [("strong", 3)])

    def test_bolds_bracketed_terms(self) -> None:
        provider = StaticUrbanProvider(
            [UrbanEntry(word="example", definition="A [linked term] in a definition.")]
        )
        self.assertIn(
            f"A {IRC_BOLD}linked term{IRC_BOLD} in a definition.",
            render_urban_command("!ud example", provider),
        )

    def test_no_entries_message_matches_logs(self) -> None:
        self.assertEqual(
            render_urban_command("!urban poka-yoke", StaticUrbanProvider([])),
            ["No entries found for 'poka-yoke'"],
        )

    def test_usage_for_non_command(self) -> None:
        self.assertEqual(render_urban_command("!urban", StaticUrbanProvider([])), ["Usage: !urban <term>"])


if __name__ == "__main__":
    unittest.main()
