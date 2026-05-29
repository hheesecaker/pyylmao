from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pyylmao.twitter as twitter
from pyylmao.twitter import (
    is_twitter_command,
    render_twitter_command,
    status_id_from_text,
    write_last_twitter_json,
)


class TwitterTests(unittest.TestCase):
    def test_detects_logged_status_url_forms_and_tool_command(self) -> None:
        self.assertEqual(
            status_id_from_text("https://x.com/HistorianUSA1/status/2052013873956352453"),
            "2052013873956352453",
        )
        self.assertEqual(
            status_id_from_text("https://nitter.net/user/status/2052013873956352453"),
            "2052013873956352453",
        )
        self.assertEqual(status_id_from_text("!twitter 2052013873956352453"), "2052013873956352453")
        self.assertTrue(is_twitter_command("!twitter https://xcancel.com/u/status/2052013873956352453"))
        self.assertFalse(is_twitter_command("2052013873956352453"))

    def test_renders_syndication_json_in_logged_shape(self) -> None:
        def fetcher(status_id: str):
            self.assertEqual(status_id, "2052013873956352453")
            return {
                "text": "POV: You already know every single hate comment coming...",
                "created_at": "Wed May 06 12:00:00 +0000 2026",
                "conversation_count": 2453,
                "retweet_count": 323,
                "favorite_count": 2341,
                "user": {"name": "DocumentingLibs", "screen_name": "HistorianUSA1"},
            }

        self.assertEqual(
            render_twitter_command("!twitter 2052013873956352453", fetcher=fetcher),
            [
                "DocumentingLibs @HistorianUSA1 May 06 2026",
                "POV: You already know every single hate comment coming...",
                "💬 2453 ♻️ 323 ❤️ 2341",
            ],
        )

    def test_raw_json_write_prefers_first_writable_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            blocked = Path(tmp) / "missing" / "first.json"
            fallback = Path(tmp) / "second.json"
            with patch.object(twitter, "LAST_JSON_PATHS", (blocked, fallback)):
                write_last_twitter_json({"text": "ok"})

            self.assertEqual(json.loads(blocked.read_text(encoding="utf-8")), {"text": "ok"})
            self.assertFalse(fallback.exists())


if __name__ == "__main__":
    unittest.main()
