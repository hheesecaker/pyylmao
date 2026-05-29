from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pyylmao.ufc import (
    HELP_LINES,
    NO_EVENTS,
    UFCEvent,
    UFCFight,
    UFCFighter,
    is_ufc_command,
    parse_ufc_options,
    render_ufc_command,
)


class FakeUFCProvider:
    def __init__(self, events: tuple[UFCEvent, ...]):
        self.events = events
        self.calls: list[tuple[datetime, datetime, bool]] = []

    def load_events(self, start: datetime, end: datetime, refresh: bool = False) -> tuple[UFCEvent, ...]:
        self.calls.append((start, end, refresh))
        return tuple(event for event in self.events if start <= event.date <= end)


def sample_event() -> UFCEvent:
    return UFCEvent(
        name="UFC 328: Chimaev vs. Strickland",
        date=datetime(2026, 5, 9, 21, 0, tzinfo=UTC),
        fights=(
            UFCFight(
                weight_class="Lightweight",
                date=datetime(2026, 5, 10, 0, 30, tzinfo=UTC),
                status="SCHEDULED",
                fighters=(
                    UFCFighter("Some Fighter", "USA", "10-1-0", "30", "5' 10\"", "155 lbs", '70"'),
                    UFCFighter("Other Fighter", "Brazil", "9-2-0", "28", "5' 9\"", "155 lbs", '71"'),
                ),
            ),
            UFCFight(
                weight_class="Middleweight",
                date=datetime(2026, 5, 10, 1, 0, tzinfo=UTC),
                status="FINAL",
                fighters=(
                    UFCFighter("Sean Strickland", "USA", "31-7-0", "35", "6' 1\"", "185 lbs", '76"', True, "143.0"),
                    UFCFighter("Khamzat Chimaev", "United Arab Emirates", "15-1-0", "32", "6' 2\"", "185 lbs", '75"', False, "142.0"),
                ),
            ),
        ),
    )


class UFCTests(unittest.TestCase):
    def test_detects_ufc_command(self) -> None:
        self.assertTrue(is_ufc_command("!ufc"))
        self.assertTrue(is_ufc_command("!ufc --filter 328 --main"))
        self.assertFalse(is_ufc_command("!ufcx --filter 328"))

    def test_help_matches_logged_shape(self) -> None:
        self.assertEqual(render_ufc_command("!ufc --help"), HELP_LINES)
        self.assertIn("--fighter [FIGHTER ...]", "\n".join(HELP_LINES))
        self.assertIn("--main                Show main event only", "\n".join(HELP_LINES))

    def test_parses_new_and_old_argument_forms(self) -> None:
        parsed = parse_ufc_options("!ufc --refresh --filter 328 --main --width 18")
        self.assertEqual(parsed.event_filters, ("328",))
        self.assertTrue(parsed.refresh)
        self.assertTrue(parsed.main)
        self.assertEqual(parsed.image_width, 18)

        old_style = parse_ufc_options("!ufc filter 325 width 14 tw 70 main True")
        self.assertEqual(old_style.event_filters, ("325",))
        self.assertEqual(old_style.image_width, 14)
        self.assertEqual(old_style.terminal_width, 70)
        self.assertTrue(old_style.main)

    def test_renders_live_card_data_from_provider(self) -> None:
        provider = FakeUFCProvider((sample_event(),))
        lines = render_ufc_command(
            "!ufc --filter 328 --main --font missing-font",
            provider=provider,
            now=datetime(2026, 4, 26, tzinfo=UTC),
        )
        output = "\n".join(lines)
        self.assertIn("UFC 328", output)
        self.assertIn("Chimaev vs. Strickland", output)
        self.assertIn("Saturday, May 09 @ 9PM EST", output)
        self.assertIn("Sean Strickland", output)
        self.assertIn("Khamzat Chimaev", output)
        self.assertIn("31-7-0", output)
        self.assertIn("REACH", output)
        self.assertEqual(len(provider.calls), 1)

    def test_no_events_message_matches_logs(self) -> None:
        provider = FakeUFCProvider((sample_event(),))
        lines = render_ufc_command(
            "!ufc --filter 999",
            provider=provider,
            now=datetime(2026, 4, 26, tzinfo=UTC),
        )
        self.assertEqual(lines, [NO_EVENTS])

    def test_fighter_filter_keeps_matching_fight(self) -> None:
        provider = FakeUFCProvider((sample_event(),))
        lines = render_ufc_command(
            "!ufc fighter Strickland font missing-font",
            provider=provider,
            now=datetime(2026, 4, 26, tzinfo=UTC),
        )
        output = "\n".join(lines)
        self.assertIn("Sean Strickland", output)
        self.assertNotIn("Some Fighter", output)


if __name__ == "__main__":
    unittest.main()
