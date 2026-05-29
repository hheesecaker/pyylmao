from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyylmao.bluesky import (
    BlueskyFeedWatcher,
    BlueskyPost,
    format_post,
    parse_post_view,
    post_matches,
    search_query_for_pattern,
)
from pyylmao.filters import FilterStore
from pyylmao.state import JsonState


class FakeBlueskyClient:
    def __init__(self, posts: list[BlueskyPost]):
        self.posts = posts
        self.queries: list[str] = []

    def search_posts(self, query: str, limit: int = 25) -> list[BlueskyPost]:
        self.queries.append(query)
        return self.posts


class BlueskyTests(unittest.TestCase):
    def test_parse_and_format_post_view(self) -> None:
        post = parse_post_view(
            {
                "uri": "at://did:plc:abc/app.bsky.feed.post/3abc",
                "author": {"handle": "alice.example"},
                "record": {"text": "hello\nworld", "createdAt": "2026-01-02T00:00:00Z"},
            }
        )
        self.assertIsNotNone(post)
        assert post is not None
        self.assertEqual(post.web_url, "https://bsky.app/profile/alice.example/post/3abc")
        self.assertEqual(
            format_post(post),
            ["hello", "world https://bsky.app/profile/alice.example/post/3abc"],
        )

    def test_regex_matching_and_search_query_cleanup(self) -> None:
        post = BlueskyPost(
            uri="at://did:plc:abc/app.bsky.feed.post/3abc",
            handle="alice.example",
            text="Somaliland news",
        )
        self.assertTrue(post_matches("(?i)somali", post))
        self.assertEqual(search_query_for_pattern(r"irc\.\w+\."), "irc.")
        self.assertEqual(search_query_for_pattern("kill myself"), "kill myself")

    def test_watcher_emits_matching_posts_once(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = JsonState(Path(tmp.name) / "state.json")
        filters = FilterStore(state)
        filters.add("kill myself")
        post = BlueskyPost(
            uri="at://did:plc:abc/app.bsky.feed.post/3abc",
            handle="alice.example",
            text="I might kill myself",
        )
        watcher = BlueskyFeedWatcher(
            filters=filters,
            state=state,
            client=FakeBlueskyClient([post]),
        )
        self.assertEqual(
            watcher.poll_once(),
            [["I might kill myself https://bsky.app/profile/alice.example/post/3abc"]],
        )
        self.assertEqual(watcher.poll_once(), [])


if __name__ == "__main__":
    unittest.main()
