from __future__ import annotations

import unittest

from pyylmao.curl import (
    CurlCommandError,
    is_curl_command,
    parse_curl_request,
    render_curl_command,
)


class StaticCurlFetcher:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.calls: list[tuple[str, int]] = []

    def fetch(self, url: str, max_bytes: int) -> bytes:
        self.calls.append((url, max_bytes))
        return self.payload


class CurlTests(unittest.TestCase):
    def test_detects_curl_commands(self) -> None:
        self.assertTrue(is_curl_command("!curl https://example.test/a.txt"))
        self.assertTrue(is_curl_command("!curl2 https://example.test/a.txt"))
        self.assertFalse(is_curl_command("!curl ftp://example.test/a.txt"))

    def test_parses_url_and_optional_rest(self) -> None:
        self.assertEqual(
            parse_curl_request("!curl https://example.test/a.txt extra").url,
            "https://example.test/a.txt",
        )
        self.assertEqual(
            parse_curl_request("!curl https://example.test/a.txt extra").rest,
            "extra",
        )

    def test_curl_preserves_blank_lines(self) -> None:
        fetcher = StaticCurlFetcher(b"one\n\ntwo")
        self.assertEqual(
            render_curl_command("!curl https://example.test/a.txt", fetcher),
            ["one", "", "two"],
        )
        self.assertEqual(fetcher.calls, [("https://example.test/a.txt", 262144)])

    def test_curl2_compacts_blank_lines(self) -> None:
        fetcher = StaticCurlFetcher(b"one\n\ntwo\n")
        self.assertEqual(
            render_curl_command("!curl2 https://example.test/a.txt", fetcher),
            ["one", "two"],
        )

    def test_truncates_long_output_like_logs(self) -> None:
        payload = "\n".join(str(item) for item in range(5)).encode()
        self.assertEqual(
            render_curl_command("!curl https://example.test/a.txt", StaticCurlFetcher(payload), max_lines=3),
            ["0", "1", "2", "error: output truncated to 3 of 5 lines total"],
        )

    def test_curl_rejects_non_utf8_payload(self) -> None:
        with self.assertRaises(CurlCommandError):
            render_curl_command("!curl https://example.test/a.ans", StaticCurlFetcher(b"\xff"))

    def test_curl2_replaces_non_utf8_payload(self) -> None:
        self.assertEqual(
            render_curl_command("!curl2 https://example.test/a.ans", StaticCurlFetcher(b"\xff")),
            ["�"],
        )


if __name__ == "__main__":
    unittest.main()
