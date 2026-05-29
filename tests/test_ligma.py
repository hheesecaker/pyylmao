from __future__ import annotations

import unittest

from pyylmao.ligma import (
    LigmaStatus,
    html_to_plain_text,
    is_ligma_command,
    parse_ligma_request,
    render_ligma_command,
    render_ligma_status,
    status_from_json,
)


class FakeLigmaClient:
    def status(self, status_id: str) -> LigmaStatus:
        self.status_id = status_id
        return LigmaStatus(
            id=status_id,
            display_name="Nietzschean Ekko Enjoyer",
            username="r000t",
            created_at="2025-10-28T19:06:27.582Z",
            content="The way society has treated me is my license to lie, cheat, and steal anything I so choose.",
            avatar_url="https://example.test/r000t.jpg",
            replies_count=2,
            reblogs_count=1,
            favourites_count=0,
        )

    def replies(self, status_id: str) -> list[LigmaStatus]:
        self.replies_status_id = status_id
        return [
            LigmaStatus(
                id="115453381",
                display_name="The Felon Pope :popephil:",
                username="Phil@freeatlantis.com",
                created_at="2025-10-28T19:10:00.000Z",
                content="@r000t So you will become what you hate and provide your victims with the potential to think the same way.",
                avatar_url="https://example.test/phil.jpg",
                replies_count=1,
                reblogs_count=0,
                favourites_count=0,
            )
        ]


class LigmaTests(unittest.TestCase):
    def test_detects_logged_link_trigger_and_all_arg(self) -> None:
        self.assertTrue(is_ligma_command("https://ligma.pro/@r000t/115453354808572799"))
        self.assertTrue(is_ligma_command("look https://ligma.pro/@r000t/115453354808572799 all"))
        self.assertFalse(is_ligma_command("https://example.test/@r000t/115453354808572799"))

        request = parse_ligma_request("https://ligma.pro/@r000t/115453354808572799 all")
        self.assertEqual(request.status_id, "115453354808572799")
        self.assertTrue(request.show_all)

    def test_status_json_uses_mastodon_fields(self) -> None:
        status = status_from_json(
            {
                "id": "115453354808572799",
                "content": "<p>Hello <a href=\"https://ligma.pro/@r000t\">@r000t</a></p>",
                "created_at": "2025-10-28T19:06:27.582Z",
                "replies_count": 2,
                "reblogs_count": 1,
                "favourites_count": 0,
                "account": {
                    "display_name": "Nietzschean Ekko Enjoyer",
                    "acct": "r000t",
                    "avatar_static": "https://example.test/r000t.jpg",
                },
            }
        )
        self.assertEqual(status.display_name, "Nietzschean Ekko Enjoyer")
        self.assertEqual(status.username, "r000t")
        self.assertEqual(status.content, "Hello @r000t")
        self.assertEqual(status.replies_count, 2)
        self.assertEqual(status.reblogs_count, 1)

    def test_html_to_plain_text_keeps_external_links_but_not_local_mentions(self) -> None:
        self.assertEqual(
            html_to_plain_text(
                '<p><a href="https://ligma.pro/@r000t">@r000t</a> see '
                '<a href="https://example.test/post">this</a></p>'
            ),
            "@r000t see this (https://example.test/post)",
        )

    def test_renders_logged_status_shape_with_avatar_and_stats(self) -> None:
        status = FakeLigmaClient().status("115453354808572799")

        def avatar(url: str) -> list[str]:
            self.assertEqual(url, "https://example.test/r000t.jpg")
            return ["AV1", "AV2", "AV3"]

        self.assertEqual(
            render_ligma_status(status, avatar_renderer=avatar),
            [
                "AV1  Nietzschean Ekko Enjoyer @r000t Oct 28 2025",
                "AV2  The way society has treated me is my license to lie, cheat,",
                "AV3  and steal anything I so choose.",
                "     💬 2 ♻️ 1 ❤️ 0",
            ],
        )

    def test_render_command_includes_indented_replies_for_all(self) -> None:
        client = FakeLigmaClient()

        def avatar(url: str) -> list[str]:
            return ["AVR"] if "r000t" in url else ["AVP"]

        lines = render_ligma_command(
            "https://ligma.pro/@r000t/115453354808572799 all",
            client=client,
            avatar_renderer=avatar,
        )
        self.assertEqual(client.status_id, "115453354808572799")
        self.assertEqual(client.replies_status_id, "115453354808572799")
        self.assertIn("AVR  Nietzschean Ekko Enjoyer @r000t Oct 28 2025", lines)
        self.assertIn("        AVP  The Felon Pope :popephil: @Phil@freeatlantis.com Oct 28 2025", lines)
        self.assertTrue(any("@r000t So you will become" in line for line in lines))


if __name__ == "__main__":
    unittest.main()
