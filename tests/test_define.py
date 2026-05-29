from __future__ import annotations

import unittest

from pyylmao.define import (
    Definition,
    DictionaryEntry,
    Meaning,
    bold_text,
    is_define_command,
    parse_define_word,
    parse_dictionary_entry,
    render_define_command,
)


class StaticDefineProvider:
    def __init__(self, entries: list[DictionaryEntry]):
        self.entries = entries
        self.calls: list[str] = []

    def lookup(self, word: str) -> list[DictionaryEntry]:
        self.calls.append(word)
        return self.entries


class DefineTests(unittest.TestCase):
    def test_detects_define_command(self) -> None:
        self.assertTrue(is_define_command("!define gay"))
        self.assertFalse(is_define_command("!defined gay"))
        self.assertFalse(is_define_command("!define"))

    def test_parses_word_or_phrase(self) -> None:
        self.assertEqual(parse_define_word("!define  gay "), "gay")
        self.assertEqual(parse_define_word("!define tick over"), "tick over")

    def test_parses_dictionary_api_shape(self) -> None:
        entry = parse_dictionary_entry(
            {
                "word": "gay",
                "phonetics": [{"text": "/ɡeɪ/"}],
                "meanings": [
                    {
                        "partOfSpeech": "noun",
                        "definitions": [
                            {
                                "definition": "A homosexual, especially a male homosexual.",
                            }
                        ],
                    }
                ],
            }
        )

        self.assertEqual(
            entry,
            DictionaryEntry(
                word="gay",
                phonetic="/ɡeɪ/",
                meanings=[
                    Meaning(
                        part_of_speech="noun",
                        definitions=[Definition("A homosexual, especially a male homosexual.")],
                    )
                ],
            ),
        )

    def test_renders_logged_markdown_definition_shape(self) -> None:
        provider = StaticDefineProvider(
            [
                DictionaryEntry(
                    word="gay",
                    phonetic="/ɡeɪ/",
                    meanings=[
                        Meaning(
                            "noun",
                            [
                                Definition(
                                    "(chiefly in plural or attributive) A homosexual, especially a male homosexual; see also lesbian."
                                ),
                                Definition("Something which is bright or colorful, such as a picture or a flower."),
                                Definition("An ornament, a knick-knack."),
                            ],
                        ),
                        Meaning(
                            "adjective",
                            [
                                Definition(
                                    "(possibly obsolete) Happy, joyful, and lively.",
                                    "The Gay Science",
                                ),
                            ],
                        ),
                    ],
                )
            ]
        )

        self.assertEqual(
            render_define_command("!define gay", provider),
            [
                "gay /ɡeɪ/",
                "",
                "𝐍𝐨𝐮𝐧",
                "",
                "",
                "  • (chiefly in plural or attributive) A homosexual, especially a male homosexual; see also lesbian.",
                "",
                "  • Something which is bright or colorful, such as a picture or a flower.",
                "",
                "  • An ornament, a knick-knack.",
                "",
                "",
                "𝐀𝐝𝐣𝐞𝐜𝐭𝐢𝐯𝐞",
                "",
                "",
                "  • (possibly obsolete) Happy, joyful, and lively.",
                "    Example: The Gay Science",
                "",
                "",
            ],
        )
        self.assertEqual(provider.calls, ["gay"])

    def test_no_definitions_message(self) -> None:
        self.assertEqual(
            render_define_command("!define agglutinization", StaticDefineProvider([])),
            ["No definitions found for 'agglutinization'"],
        )

    def test_usage_for_non_command(self) -> None:
        self.assertEqual(render_define_command("!define", StaticDefineProvider([])), ["Usage: !define <word>"])

    def test_bold_text_matches_logged_headings(self) -> None:
        self.assertEqual(bold_text("Noun"), "𝐍𝐨𝐮𝐧")


if __name__ == "__main__":
    unittest.main()
