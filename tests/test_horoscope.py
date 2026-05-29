from __future__ import annotations

import unittest

from pyylmao.horoscope import (
    HoroscopeError,
    is_horoscope_command,
    parse_horoscope_sign,
    render_horoscope_command,
)


class FakeProvider:
    def __init__(self, reply: str = "Today is unusually specific.", error: Exception | None = None):
        self.reply = reply
        self.error = error
        self.calls: list[str] = []

    def fetch(self, sign: str) -> str:
        self.calls.append(sign)
        if self.error is not None:
            raise self.error
        return self.reply


class HoroscopeTests(unittest.TestCase):
    def test_detects_dot_prefixed_logged_command(self) -> None:
        self.assertTrue(is_horoscope_command(".horoscope leo"))
        self.assertTrue(is_horoscope_command(".horoscope"))
        self.assertFalse(is_horoscope_command("!horoscope leo"))
        self.assertFalse(is_horoscope_command(".horoscopes leo"))

    def test_parses_optional_sign_without_aliasing_short_names(self) -> None:
        self.assertEqual(parse_horoscope_sign(".horoscope leo"), "leo")
        self.assertEqual(parse_horoscope_sign(".horoscope Capricorn"), "capricorn")
        self.assertIsNone(parse_horoscope_sign(".horoscope"))
        self.assertEqual(parse_horoscope_sign(".horoscope cap"), "cap")

    def test_renders_provider_horoscope_for_full_sign(self) -> None:
        provider = FakeProvider("Leo, beware of odd impressions.")
        self.assertEqual(
            render_horoscope_command(".horoscope leo", "tinky", provider),
            ["Leo, beware of odd impressions."],
        )
        self.assertEqual(provider.calls, ["leo"])

    def test_missing_short_and_unknown_signs_use_logged_error_shape(self) -> None:
        provider = FakeProvider()
        self.assertEqual(
            render_horoscope_command(".horoscope", "malcom", provider),
            ["Sorry, malcom, couldn't fetch the horoscope for None."],
        )
        self.assertEqual(
            render_horoscope_command(".horoscope cap", "lain", provider),
            ["Sorry, lain, couldn't fetch the horoscope for cap."],
        )
        self.assertEqual(
            render_horoscope_command(".horoscope pizza", "Zodiac", provider),
            ["Sorry, Zodiac, couldn't fetch the horoscope for pizza."],
        )
        self.assertEqual(provider.calls, [])

    def test_provider_errors_use_logged_error_shape(self) -> None:
        self.assertEqual(
            render_horoscope_command(".horoscope leo", "alice", FakeProvider(error=HoroscopeError("offline"))),
            ["Sorry, alice, couldn't fetch the horoscope for leo."],
        )
