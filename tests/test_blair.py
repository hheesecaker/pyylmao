from __future__ import annotations

import unittest

from pyylmao.blair import (
    BlairPost,
    BlairReply,
    html_to_text,
    is_blair2_command,
    is_blair_command,
    render_blair2_command,
    render_blair_command,
)


class FakeBlairClient:
    def pinned_posts(self, limit: int = 12) -> list[BlairPost]:
        return [
            BlairPost(
                id="1",
                content="<p>The way society has treated me is my license to lie, cheat, and steal anything I so choose.</p>",
                created_at="2025-10-28T19:06:27.582Z",
                replies_count=2,
                url="https://ligma.pro/@r000t/1",
            ),
            BlairPost(
                id="2",
                content="<p>When I said Ekko means everything to me, I meant it.</p>",
                created_at="2024-09-16T23:52:38.552Z",
                replies_count=0,
                url="https://ligma.pro/@r000t/2",
            ),
        ]

    def replies(self, status_id: str, limit: int = 3) -> list[BlairReply]:
        if status_id == "1":
            return [
                BlairReply('<p><span class="h-card"><a href="https://ligma.pro/@r000t">@<span>r000t</span></a></span> make that guy angrier...</p>')
            ]
        return []


class BlairTests(unittest.TestCase):
    def test_detects_historical_triggers(self) -> None:
        self.assertTrue(is_blair_command("!blair"))
        self.assertFalse(is_blair_command("!blair last 3"))
        self.assertTrue(is_blair2_command("!blair2"))
        self.assertTrue(is_blair2_command("!blair2 anything"))
        self.assertFalse(is_blair2_command("!blair"))

    def test_html_to_text_decodes_paragraphs_and_mentions(self) -> None:
        self.assertEqual(
            html_to_text('<p>Some loser &amp; cops.</p><p><a href="https://ligma.pro/@r000t">@<span>r000t</span></a> ok</p>'),
            "Some loser & cops.\n@r000t (https://ligma.pro/@r000t) ok",
        )

    def test_blair_renders_cleaned_posts_and_replies(self) -> None:
        lines = render_blair_command("!blair", FakeBlairClient())
        self.assertEqual(lines[0], "Posts from @r000t@ligma.pro (up to 12):")
        self.assertIn("Post 1:", lines)
        self.assertIn("The way society has treated me is my license to lie, cheat, and steal anything I so choose.", lines)
        self.assertIn("Replies: 2", lines)
        self.assertIn("  Reply: @r000t (https://ligma.pro/@r000t) make that guy angrier...", lines)

    def test_blair2_renders_logged_raw_content_style(self) -> None:
        lines = render_blair2_command("!blair2", FakeBlairClient())
        self.assertEqual(lines[0], "Posts from @r000t@ligma.pro (up to 12):")
        self.assertIn("Post 1:", lines)
        self.assertTrue(any("<p>The way society" in line for line in lines))
        self.assertIn("Replies: 2", lines)


if __name__ == "__main__":
    unittest.main()
