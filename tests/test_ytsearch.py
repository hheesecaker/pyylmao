from __future__ import annotations

import re
import unittest

from pyylmao.link_preview import IRC_BOLD, IRC_RESET
from pyylmao.ytsearch import render_ytsearch_command


IRC_COLOR_RE = re.compile(r"\x03\d{0,2}(?:,\d{1,2})?")


def strip_irc_codes(text: str) -> str:
    return IRC_COLOR_RE.sub("", text).replace(IRC_BOLD, "").replace(IRC_RESET, "")


class YTSearchTests(unittest.TestCase):
    def test_render_ytsearch_results_match_logged_two_line_shape(self) -> None:
        def fetcher(query: str, max_results: int):
            self.assertEqual(query, "im not okay")
            self.assertEqual(max_results, 5)
            return (
                {
                    "items": [
                        {
                            "id": {"kind": "youtube#video", "videoId": "dhZTNgAs4Fc"},
                            "snippet": {
                                "publishedAt": "2010-02-26T00:00:00Z",
                                "title": "My Chemical Romance - I&#39;m Not Okay",
                                "description": "Watch the official 4k film restored music video.",
                                "channelTitle": "My Chemical Romance",
                            },
                        }
                    ]
                },
                {
                    "items": [
                        {
                            "id": "dhZTNgAs4Fc",
                            "contentDetails": {"duration": "PT3M26S"},
                            "statistics": {"viewCount": "142300000", "likeCount": "1300000"},
                        }
                    ]
                },
            )

        lines = [strip_irc_codes(line) for line in render_ytsearch_command("!yt im not okay", fetcher)]

        self.assertEqual(
            lines,
            [
                " ▶  My Chemical Romance - I'm Not Okay | My Chemical Romance [3:26] 142.3M views 1.3M likes",
                "  Published: 2010-02-26 | Watch the official 4k film restored music video. | https://youtu.be/dhZTNgAs4Fc",
            ],
        )


if __name__ == "__main__":
    unittest.main()
