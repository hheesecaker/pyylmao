from __future__ import annotations

import re
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from pyylmao.link_preview import (
    IRC_BOLD,
    IRC_COLOR,
    IRC_RESET,
    YouTubePreview,
    compact_count,
    fetch_youtube_preview,
    fetch_youtube_innertube,
    first_url,
    format_youtube_date,
    format_duration,
    is_youtube_url,
    parse_youtube_initial_data,
    relative_youtube_date,
    render_youtube_preview,
)


IRC_COLOR_RE = re.compile(r"\x03\d{0,2}(?:,\d{1,2})?")


def strip_irc_codes(text: str) -> str:
    return IRC_COLOR_RE.sub("", text).replace(IRC_BOLD, "").replace(IRC_RESET, "")


class LinkPreviewTests(unittest.TestCase):
    def test_first_url_trims_common_trailing_punctuation(self) -> None:
        self.assertEqual(
            first_url("watch this (https://example.test/path)."),
            "https://example.test/path",
        )

    def test_detects_youtube_urls(self) -> None:
        self.assertTrue(is_youtube_url("https://youtu.be/tq17_LlJCSo?t=655"))
        self.assertTrue(is_youtube_url("https://www.youtube.com/watch?v=tq17_LlJCSo"))
        self.assertFalse(is_youtube_url("https://example.test/watch?v=tq17_LlJCSo"))

    def test_renders_log_style_youtube_preview_with_stats(self) -> None:
        rendered = render_youtube_preview(
            YouTubePreview(
                title="HE LOST HIS MIND..",
                author="Asmongold TV",
                duration_seconds=2055,
                view_count=105_000,
                like_count=8_000,
            )
        )
        self.assertEqual(
            rendered,
            (
                f"{IRC_COLOR}0,4 ▶ {IRC_RESET} {IRC_COLOR}1,15 HE LOST HIS MIND.. | Asmongold TV {IRC_RESET} "
                f"{IRC_COLOR}1,15[00:34:15]{IRC_RESET} "
                f"{IRC_COLOR}1,15 {IRC_BOLD}105K{IRC_BOLD} views {IRC_COLOR} "
                f"{IRC_COLOR}1,15 {IRC_BOLD}8K{IRC_BOLD} likes {IRC_RESET}"
            ),
        )
        self.assertEqual(
            strip_irc_codes(rendered),
            " ▶   HE LOST HIS MIND.. | Asmongold TV  [00:34:15]  105K views   8K likes ",
        )

    def test_renders_log_style_youtube_preview_with_upload_date_island(self) -> None:
        rendered = render_youtube_preview(
            YouTubePreview(
                title="The Sam Hyde Show: Looksmaxxing feat. Androgenic",
                author="Sam Hyde",
                duration_seconds=3641,
                view_count=59_000,
                like_count=4_000,
                upload_date="20260403",
            )
        )
        self.assertEqual(
            rendered,
            (
                f"{IRC_COLOR}0,4 ▶ {IRC_RESET} "
                f"{IRC_COLOR}1,15 The Sam Hyde Show: Looksmaxxing feat. Androgenic | Sam Hyde {IRC_RESET} "
                f"{IRC_COLOR}1,15[01:00:41]{IRC_RESET} "
                f"{IRC_COLOR}1,15 {IRC_BOLD}59K{IRC_BOLD} views {IRC_COLOR} "
                f"{IRC_COLOR}1,15 {IRC_BOLD}4K{IRC_BOLD} likes {IRC_RESET} "
                f"{IRC_COLOR}1,15 {IRC_BOLD}Apr 03, 2026{IRC_BOLD}{IRC_RESET}"
            ),
        )
        self.assertEqual(
            strip_irc_codes(rendered),
            " ▶   The Sam Hyde Show: Looksmaxxing feat. Androgenic | Sam Hyde  [01:00:41]  59K views   4K likes   Apr 03, 2026",
        )

    def test_renders_stats_only_islands_with_logged_spacing(self) -> None:
        rendered = render_youtube_preview(
            YouTubePreview(
                title="The Voice Actors In Your Headphones",
                author="String and Tell",
                view_count=1_489_635,
                like_count=69_000,
                upload_date="May 2, 2026",
            )
        )
        self.assertEqual(
            strip_irc_codes(rendered),
            " ▶   The Voice Actors In Your Headphones | String and Tell   1.5M views   69K likes   May 02, 2026",
        )

    def test_renders_live_and_upcoming_statuses(self) -> None:
        live = render_youtube_preview(
            YouTubePreview(
                title="The Red Pill is Teaching Men to be Fruity",
                author="Brittany Venti",
                live_status="is_live",
                view_count=364,
                like_count=124,
            )
        )
        self.assertIn("[LIVE]  364 views   124 likes", strip_irc_codes(live))
        upcoming = render_youtube_preview(
            YouTubePreview(
                title="The Red Pill is Teaching Men to be Fruity",
                author="Brittany Venti",
                live_status="is_upcoming",
                view_count=0,
                like_count=68,
            )
        )
        self.assertIn("[UPCOMING]  0 views   68 likes", strip_irc_codes(upcoming))

    def test_count_and_duration_formatting(self) -> None:
        self.assertEqual(format_duration(65), "00:01:05")
        self.assertEqual(format_duration(6_362), "01:46:02")
        self.assertEqual(compact_count(703), "703")
        self.assertEqual(compact_count(18_000), "18K")
        self.assertEqual(compact_count(3_000_000), "3.0M")
        self.assertEqual(format_youtube_date("20260403"), "Apr 03, 2026")
        self.assertEqual(format_youtube_date("2026-04-03T07:00:00Z"), "Apr 03, 2026")
        self.assertEqual(format_youtube_date("2009-10-24T23:57:33-07:00"), "Oct 25, 2009")
        self.assertEqual(format_youtube_date("May 2, 2026"), "May 02, 2026")
        self.assertEqual(format_youtube_date("2 May 2026"), "May 02, 2026")
        self.assertEqual(
            relative_youtube_date(
                "Premiered 15 hours ago",
                now=datetime(2026, 5, 29, 10, 0, tzinfo=timezone.utc),
            ),
            "May 28, 2026",
        )

    def test_parses_youtube_web_header_metadata_when_player_is_blocked(self) -> None:
        html = """
        <script>
        var ytInitialData = {"engagementPanels":[{"videoDescriptionHeaderRenderer":{
          "title":{"runs":[{"text":"The Voice Actors In Your Headphones"}]},
          "channel":{"simpleText":"String and Tell"},
          "views":{"simpleText":"1,489,635 views"},
          "publishDate":{"simpleText":"May 2, 2026"},
          "factoid":[
            {"factoidRenderer":{
              "value":{"simpleText":"69K"},
              "label":{"simpleText":"Likes"},
              "accessibilityText":"69 thousand likes"
            }},
            {"factoidRenderer":{
              "value":{"simpleText":"May 2"},
              "label":{"simpleText":"2026"},
              "accessibilityText":"May 2, 2026"
            }}
          ]
        }}]};
        </script>
        """
        preview = parse_youtube_initial_data(html)
        self.assertEqual(
            preview,
            YouTubePreview(
                title="The Voice Actors In Your Headphones",
                author="String and Tell",
                view_count=1_489_635,
                like_count=69_000,
                upload_date="May 02, 2026",
            ),
        )

    def test_fetch_youtube_preview_enriches_partial_sources(self) -> None:
        with (
            patch(
                "pyylmao.link_preview.fetch_youtube_with_ytdlp",
                return_value=YouTubePreview(
                    title="The Voice Actors In Your Headphones",
                    author="String and Tell",
                ),
            ),
            patch("pyylmao.link_preview.fetch_youtube_innertube", return_value=None),
            patch(
                "pyylmao.link_preview.fetch_youtube_web_metadata",
                return_value=YouTubePreview(
                    title="The Voice Actors In Your Headphones",
                    author="String and Tell",
                    view_count=1_489_635,
                    like_count=69_000,
                    upload_date="May 02, 2026",
                ),
            ),
            patch("pyylmao.link_preview.fetch_youtube_oembed", side_effect=AssertionError),
        ):
            preview = fetch_youtube_preview("https://www.youtube.com/shorts/RJbIE7ITDqc")

        self.assertEqual(preview.view_count, 1_489_635)
        self.assertEqual(preview.like_count, 69_000)
        self.assertEqual(preview.upload_date, "May 02, 2026")

    def test_innertube_fallback_reads_date_and_stats(self) -> None:
        payload = {
            "videoDetails": {
                "title": "Rick Astley - Never Gonna Give You Up",
                "author": "Rick Astley",
                "lengthSeconds": "213",
                "viewCount": "1777323345",
                "isLiveContent": False,
            },
            "microformat": {
                "playerMicroformatRenderer": {
                    "uploadDate": "2009-10-24T23:57:33-07:00",
                }
            },
        }

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self, *_):
                import json

                return json.dumps(payload).encode("utf-8")

        with (
            patch("pyylmao.link_preview.urllib.request.urlopen", return_value=Response()),
            patch("pyylmao.link_preview.fetch_return_youtube_dislike_stats", return_value={"like_count": 19_124_993}),
        ):
            preview = fetch_youtube_innertube("https://youtu.be/dQw4w9WgXcQ")

        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertEqual(preview.duration_seconds, 213)
        self.assertEqual(preview.view_count, 1_777_323_345)
        self.assertEqual(preview.like_count, 19_124_993)
        self.assertEqual(preview.upload_date, "Oct 25, 2009")


if __name__ == "__main__":
    unittest.main()
