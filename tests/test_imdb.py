from __future__ import annotations

import unittest

from pyylmao.imdb import (
    ImdbCommandError,
    ImdbTitle,
    is_imdb_command,
    parse_imdb_command,
    render_imdb_command,
    stars_for_rating,
    title_from_meta,
)


class FakeProvider:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.queries: list[str] = []

    def lookup(self, query: str) -> ImdbTitle:
        self.queries.append(query)
        if self.error is not None:
            raise self.error
        return ImdbTitle(
            imdb_id="tt2798920",
            title="Annihilation",
            year="2018",
            runtime="115 min",
            genres=("Adventure", "Drama", "Horror"),
            plot="A biologist signs up for a dangerous, secret expedition.",
            directors=("Alex Garland",),
            writers=("Alex Garland", "Jeff VanderMeer"),
            cast=("Natalie Portman", "Jennifer Jason Leigh", "Tessa Thompson"),
            imdb_rating="6.8",
            box_office="$43,070,915",
        )


class ImdbTests(unittest.TestCase):
    def test_detects_logged_command_pattern(self) -> None:
        self.assertTrue(is_imdb_command("!imdb annihilation"))
        self.assertTrue(is_imdb_command("!imdb24 wuthering heights"))
        self.assertFalse(is_imdb_command(".imdb bugonia"))
        self.assertFalse(is_imdb_command("!imdb"))

    def test_parse_query_and_ignores_art_width_prefix(self) -> None:
        request = parse_imdb_command("!imdb12 bad thoughts")
        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.query, "bad thoughts")

    def test_render_uses_logged_metadata_fields(self) -> None:
        provider = FakeProvider()
        lines = render_imdb_command("!imdb annihilation", provider=provider)
        self.assertEqual(provider.queries, ["annihilation"])
        self.assertEqual(lines[0], "Annihilation (2018) https://www.imdb.com/title/tt2798920/")
        self.assertIn("Runtime: 115 min", lines)
        self.assertIn("Genre: Adventure, Drama, Horror", lines)
        self.assertIn("Director: Alex Garland", lines)
        self.assertIn("Writer: Alex Garland, Jeff VanderMeer", lines)
        self.assertIn("Starring: Natalie Portman, Jennifer Jason Leigh, Tessa Thompson", lines)
        self.assertIn("Ratings:", lines)
        self.assertIn("Internet Movie Database: ★ ★ ★ ★ ★ ★ ★ ☆ ☆ ☆ (6.8/10)", lines)
        self.assertIn("Box Office: $43,070,915", lines)

    def test_provider_errors_are_normalized(self) -> None:
        with self.assertRaises(ImdbCommandError):
            render_imdb_command("!imdb missing", provider=FakeProvider(error=ImdbCommandError("nope")))

    def test_title_from_cinemeta_schema(self) -> None:
        title = title_from_meta(
            "tt2798920",
            {
                "name": "Annihilation",
                "year": "2018",
                "runtime": "115 min",
                "genre": ["Adventure", "Drama", "Horror"],
                "description": "A biologist signs up.",
                "director": ["Alex Garland"],
                "writer": ["Alex Garland", "Jeff VanderMeer"],
                "cast": ["Natalie Portman", "Jennifer Jason Leigh", "Tessa Thompson", "Oscar Isaac"],
                "imdbRating": "6.8",
            },
        )
        self.assertEqual(title.cast, ("Natalie Portman", "Jennifer Jason Leigh", "Tessa Thompson"))
        self.assertEqual(title.imdb_rating, "6.8")

    def test_stars_for_rating(self) -> None:
        self.assertEqual(stars_for_rating("6.8"), "★ ★ ★ ★ ★ ★ ★ ☆ ☆ ☆")
        self.assertEqual(stars_for_rating("N/A"), "N/A")


if __name__ == "__main__":
    unittest.main()
