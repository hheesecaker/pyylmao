from __future__ import annotations

import unittest
from io import BytesIO
from unittest.mock import patch

from pyylmao.zscore import (
    ANU_PREFETCH_BYTES,
    fetch_anu_uint8,
    is_zscore_command,
    render_meter,
    render_zscore_command,
)


class StaticBitSource:
    def __init__(self, coin: int, bits: list[int]):
        self.coin = coin
        self._bits = bits

    def coin_flip(self) -> int:
        return self.coin

    def bit_count(self) -> int:
        return len(self._bits)

    def bits(self, count: int) -> list[int]:
        self.requested_count = count
        return self._bits


class ZScoreTests(unittest.TestCase):
    def test_detects_zscore_commands(self) -> None:
        self.assertTrue(is_zscore_command("!zscore buy NVDA??"))
        self.assertTrue(is_zscore_command("!z should i switch"))
        self.assertFalse(is_zscore_command("!zip"))

    def test_render_normal_outlook(self) -> None:
        source = StaticBitSource(0, [0, 1] * 148)
        self.assertEqual(
            render_zscore_command("!zscore", source),
            [
                "Coin flip (QRNG): 0 → excess 0s = positive.",
                "bits=296: zeros=148 ones=148",
                "████████████▌            ",
                "outlook normal (p=50.00%) bits=296",
            ],
        )

    def test_render_directional_outlook(self) -> None:
        source = StaticBitSource(1, [1] * 154 + [0] * 142)
        lines = render_zscore_command("!zscore should i switch to kde", source)
        self.assertEqual(lines[0], "Coin flip (QRNG): 1 → excess 1s = positive.")
        self.assertEqual(lines[1], "bits=296: zeros=142 ones=154")
        self.assertEqual(lines[3], "outlook very slightly positive (p=24.27%) bits=296")

    def test_meter_has_stable_width(self) -> None:
        self.assertEqual(len(render_meter(0, 296)), 25)
        self.assertEqual(len(render_meter(50, 296)), 25)
        self.assertEqual(len(render_meter(-50, 296)), 25)

    def test_default_source_fetches_anu_qrng(self) -> None:
        with patch("pyylmao.zscore.fetch_anu_uint8") as fetch:
            fetch.return_value = [1, 5, *([255] * (ANU_PREFETCH_BYTES - 2))]
            lines = render_zscore_command("!zscore")

        self.assertEqual(fetch.call_args_list[0].args, (ANU_PREFETCH_BYTES,))
        self.assertEqual(len(fetch.call_args_list), 1)
        self.assertEqual(lines[0], "Coin flip (QRNG): 1 → excess 1s = positive.")
        self.assertEqual(lines[1], "bits=296: zeros=0 ones=296")

    def test_fetch_anu_uint8_parses_json_api(self) -> None:
        class Response(BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

        with patch("pyylmao.zscore.urlopen", return_value=Response(b'{"success": true, "data": [3, 255]}')):
            self.assertEqual(fetch_anu_uint8(2), [3, 255])

    def test_fetch_anu_uint8_uses_current_api_key_when_configured(self) -> None:
        class Response(BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

        seen = []

        def fake_urlopen(request, timeout):
            seen.append(request)
            return Response(b'{"success": true, "data": [4]}')

        with patch.dict("os.environ", {"PYYLMAO_ANU_QRNG_API_KEY": "secret"}, clear=False):
            with patch("pyylmao.zscore.urlopen", side_effect=fake_urlopen):
                self.assertEqual(fetch_anu_uint8(1), [4])

        self.assertEqual(seen[0].full_url, "https://api.quantumnumbers.anu.edu.au?length=1&type=uint8")
        self.assertEqual(seen[0].headers["X-api-key"], "secret")

    def test_qrng_errors_render_like_logged_url_errors(self) -> None:
        with patch("pyylmao.zscore.fetch_anu_uint8", side_effect=TimeoutError("timed out")):
            self.assertEqual(render_zscore_command("!zscore"), ["URL Error: timed out"])


if __name__ == "__main__":
    unittest.main()
