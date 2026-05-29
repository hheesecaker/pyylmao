from __future__ import annotations

import unittest

from pyylmao.nostr import (
    NostrPost,
    is_nostr_command,
    parse_nostr_reference,
    render_nostr_command,
)


LOG_NEVENT = (
    "nevent1qqs9h777vva2rk9ek5jv0gm86fhgjp5rf0w2hvlaryzsav4rh4d7efgzypm89"
    "suamzkxrut22tup279la0d4lrrsh3d8yam9d26m5eamty84sqcyqqqqqqgpz3mhxue69"
    "uhhyetvv9ujuerpd46hxtnfduq3vamnwvaz7tmcd4ezuatnv4hx7um5wghxjargw4e8"
    "gumhdpjku6ts9ejk2umr9lu"
)


class NostrTests(unittest.TestCase):
    def test_parses_logged_nevent_reference(self) -> None:
        ref = parse_nostr_reference(LOG_NEVENT)
        self.assertEqual(
            ref.event_id,
            "5bfbde633aa1d8b9b524c7a367d26e8906834bdcabb3fd19050eb2a3bd5beca5",
        )
        self.assertEqual(
            ref.author,
            "7672c39dd8ac61f16a52f81578bfebdb5f8c70bc5a7277656ab5ba67bb590f58",
        )
        self.assertEqual(ref.kind, 1)
        self.assertIn("wss://relay.damus.io", ref.relays)

    def test_detects_nostr_command(self) -> None:
        self.assertTrue(is_nostr_command(f"nostr:{LOG_NEVENT}"))
        self.assertTrue(is_nostr_command("nostr:5bfbde633aa1d8b9b524c7a367d26e8906834bdcabb3fd19050eb2a3bd5beca5"))
        self.assertFalse(is_nostr_command("https://nostr.example/not-a-command"))

    def test_renders_post_with_avatar_in_logged_shape(self) -> None:
        def fetcher(ref):
            self.assertEqual(ref.event_id, "5bfbde633aa1d8b9b524c7a367d26e8906834bdcabb3fd19050eb2a3bd5beca5")
            return NostrPost(
                event_id=ref.event_id,
                author=ref.author,
                created_at=1776587757,
                kind=1,
                content=(
                    "RFK summoned to the Oval Office to administer DMT intravenously to the president.\n"
                    "https://image.nostr.build/41760d111590f9381a544be9bcd47a580ff296ae572d67692745426c75b51151.jpg"
                ),
                profile={"display_name": "weev", "name": "weev", "picture": "https://example.test/avatar.jpg"},
            )

        def avatar_renderer(url: str) -> list[str]:
            self.assertEqual(url, "https://example.test/avatar.jpg")
            return ["AVATAR1", "AVATAR2"]

        self.assertEqual(
            render_nostr_command(f"nostr:{LOG_NEVENT}", fetcher=fetcher, avatar_renderer=avatar_renderer),
            [
                "AVATAR1  weev @weev Apr 19 2026",
                "AVATAR2  RFK summoned to the Oval Office to administer DMT intravenously to",
                "         the president.",
                "         https://image.nostr.build/41760d111590f9381a544be9bcd47a580ff296ae572d67692745426c75b51151.jpg",
            ],
        )


if __name__ == "__main__":
    unittest.main()
