from __future__ import annotations

import unittest

from pyylmao.summary import (
    SummarySource,
    build_summary_prompt,
    is_summary_command,
    parse_summary_command,
    youtube_video_id,
)


class SummaryTests(unittest.TestCase):
    def test_detects_summary_and_wsummary_commands(self) -> None:
        self.assertTrue(is_summary_command("!summary https://example.test"))
        self.assertTrue(is_summary_command("! wsummary https://example.test"))
        self.assertFalse(is_summary_command("!summaryfoo https://example.test"))

    def test_parse_summary_url_and_instruction(self) -> None:
        request = parse_summary_command(
            "!summary https://youtu.be/TD_IK7H60iA bullet points"
        )
        self.assertEqual(request.url, "https://youtu.be/TD_IK7H60iA")
        self.assertEqual(request.instruction, "bullet points")

    def test_parse_bare_domain_and_fallback_url(self) -> None:
        request = parse_summary_command("!wsummary www.example.test explain this")
        self.assertEqual(request.url, "https://www.example.test")
        self.assertEqual(request.instruction, "explain this")
        fallback = parse_summary_command("!summary latest please", "https://example.test/a")
        self.assertEqual(fallback.url, "https://example.test/a")
        self.assertEqual(fallback.instruction, "latest please")

    def test_youtube_video_id_variants(self) -> None:
        self.assertEqual(youtube_video_id("https://youtu.be/TD_IK7H60iA?t=10"), "TD_IK7H60iA")
        self.assertEqual(
            youtube_video_id("https://www.youtube.com/watch?v=TD_IK7H60iA"),
            "TD_IK7H60iA",
        )
        self.assertEqual(
            youtube_video_id("https://www.youtube.com/live/TodatmG1WlA"),
            "TodatmG1WlA",
        )
        self.assertIsNone(youtube_video_id("https://example.test/TD_IK7H60iA"))

    def test_build_summary_prompt_uses_source_content(self) -> None:
        source = SummarySource(
            url="https://example.test",
            kind="webpage",
            title="Example Title",
            text="important content",
        )
        prompt = build_summary_prompt(source, "make bullets")
        self.assertIn("make bullets", prompt)
        self.assertIn("Example Title", prompt)
        self.assertIn("important content", prompt)


if __name__ == "__main__":
    unittest.main()
