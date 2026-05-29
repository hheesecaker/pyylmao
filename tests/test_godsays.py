from __future__ import annotations

import unittest

from pyylmao.godsays import (
    format_godsays_words,
    is_godsays_command,
    parse_godsays_count,
    render_godsays_command,
)


class CyclingRng:
    def __init__(self):
        self.items = ["finger", "Darren", "EUR", "books"]
        self.index = 0

    def choice(self, values):
        value = self.items[self.index % len(self.items)]
        self.index += 1
        return value


class GodSaysTests(unittest.TestCase):
    def test_detects_inventory_pattern(self) -> None:
        self.assertTrue(is_godsays_command("!godsays"))
        self.assertTrue(is_godsays_command("!godsays 7"))
        self.assertTrue(is_godsays_command("!GODSAYS 100"))
        self.assertFalse(is_godsays_command("!godsays give me a good idea"))
        self.assertFalse(is_godsays_command("!godsays x"))

    def test_count_defaults_and_clamps(self) -> None:
        self.assertEqual(parse_godsays_count("!godsays"), 20)
        self.assertEqual(parse_godsays_count("!godsays 3"), 3)
        self.assertEqual(parse_godsays_count("!godsays 0"), 1)
        self.assertEqual(parse_godsays_count("!godsays 100"), 40)

    def test_renders_quoted_words_and_meaning(self) -> None:
        lines = render_godsays_command(
            "!godsays 4",
            rng=CyclingRng(),
            meaning_provider=lambda words: " ".join(reversed(words)),
        )
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith('" '))
        self.assertTrue(lines[0].endswith('"'))
        self.assertEqual(lines[0].count("  "), 3)
        self.assertEqual(lines[1], "Meaning: books EUR Darren finger")

    def test_formats_logged_word_spacing(self) -> None:
        self.assertEqual(
            format_godsays_words(["finger", "Darren", "EUR"]),
            '" finger  Darren  EUR"',
        )


if __name__ == "__main__":
    unittest.main()
