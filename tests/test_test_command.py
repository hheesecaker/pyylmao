from __future__ import annotations

import unittest

from pyylmao.test_command import is_test_command, parse_test_args, render_test_command


class TestCommandTests(unittest.TestCase):
    def test_detects_test_command_with_arguments(self) -> None:
        self.assertTrue(is_test_command("!test bla"))
        self.assertFalse(is_test_command("!test"))
        self.assertFalse(is_test_command("!teste bla"))

    def test_parses_whitespace_separated_args(self) -> None:
        self.assertEqual(parse_test_args("!test hello world"), ["hello", "world"])

    def test_renders_logged_challenge_response(self) -> None:
        self.assertEqual(
            render_test_command("!test bla", lambda: 9194),
            [
                "your args:",
                "0 - bla",
                "relay this code in your response: 9194",
            ],
        )

    def test_pads_short_codes_to_four_digits(self) -> None:
        self.assertEqual(
            render_test_command("!test hello world", lambda: 42),
            [
                "your args:",
                "0 - hello",
                "1 - world",
                "relay this code in your response: 0042",
            ],
        )


if __name__ == "__main__":
    unittest.main()
