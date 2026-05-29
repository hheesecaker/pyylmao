from __future__ import annotations

import json
import math
import os
import re
import secrets
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


METER_WIDTH = 25
PARTIAL_BLOCKS = ("", "▏", "▎", "▍", "▌", "▋", "▊", "▉")
ANU_QRNG_URL = "https://qrng.anu.edu.au/API/jsonI.php"
AQN_QRNG_URL = "https://api.quantumnumbers.anu.edu.au"
MAX_ZSCORE_BITS = 336
ANU_PREFETCH_BYTES = 2 + math.ceil(MAX_ZSCORE_BITS / 8)


class BitSource(Protocol):
    def coin_flip(self) -> int:
        ...

    def bit_count(self) -> int:
        ...

    def bits(self, count: int) -> list[int]:
        ...


class EntropyBitSource:
    def __init__(self):
        self.rng = secrets.SystemRandom()

    def coin_flip(self) -> int:
        return self.rng.randrange(2)

    def bit_count(self) -> int:
        return 256 + 8 * self.rng.randrange(11)

    def bits(self, count: int) -> list[int]:
        value = self.rng.getrandbits(count)
        return [(value >> index) & 1 for index in range(count)]


class QRNGError(RuntimeError):
    pass


class ANUQRNGBitSource:
    def __init__(self):
        self._values: list[int] | None = None

    def coin_flip(self) -> int:
        return self._prefetched()[0] & 1

    def bit_count(self) -> int:
        return 256 + 8 * (self._prefetched()[1] % 11)

    def bits(self, count: int) -> list[int]:
        byte_count = math.ceil(count / 8)
        values = self._prefetched()[2 : 2 + byte_count]
        bits: list[int] = []
        for value in values:
            bits.extend((value >> shift) & 1 for shift in range(7, -1, -1))
        return bits[:count]

    def _prefetched(self) -> list[int]:
        if self._values is None:
            self._values = fetch_anu_uint8(ANU_PREFETCH_BYTES)
        return self._values


def is_zscore_command(text: str) -> bool:
    return bool(re.match(r"^!z(?:score)?(?:\s+.*)?$", text.strip(), flags=re.IGNORECASE))


def render_zscore_command(text: str, bit_source: BitSource | None = None) -> list[str]:
    if not is_zscore_command(text):
        return ["Usage: !zscore [question]"]
    source = bit_source or ANUQRNGBitSource()
    try:
        coin = source.coin_flip()
        count = source.bit_count()
        bits = source.bits(count)
    except (QRNGError, HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return [f"URL Error: {exc}"]
    if len(bits) != count:
        return [f"QRNG error: expected {count} bits, got {len(bits)}"]

    ones = sum(1 for bit in bits if bit)
    zeros = count - ones
    diff = abs(zeros - ones)
    p_value = 50.0 * math.erfc(diff / math.sqrt(2 * count))
    positive_excess = (ones - zeros) if coin else (zeros - ones)

    positive_side = "1s" if coin else "0s"
    return [
        f"Coin flip (QRNG): {coin} → excess {positive_side} = positive.",
        f"bits={count}: zeros={zeros} ones={ones}",
        render_meter(positive_excess, count),
        f"outlook {outlook_label(positive_excess, p_value)} (p={p_value:.2f}%) bits={count}",
    ]


def outlook_label(positive_excess: int, p_value: float) -> str:
    if positive_excess == 0:
        return "normal"
    if p_value >= 30.0:
        return "unsure"
    direction = "positive" if positive_excess > 0 else "negative"
    if p_value >= 20.0:
        strength = "very slightly"
    elif p_value >= 10.0:
        strength = "slightly"
    elif p_value >= 5.0:
        strength = "somewhat"
    elif p_value >= 2.0:
        strength = "moderately"
    else:
        strength = "strongly"
    return f"{strength} {direction}"


def render_meter(positive_excess: int, bit_count: int) -> str:
    if bit_count <= 0:
        position = METER_WIDTH / 2
    else:
        shift = min((METER_WIDTH / 2) - 1, abs(positive_excess) / math.sqrt(bit_count))
        if positive_excess > 0:
            position = (METER_WIDTH / 2) - shift
        else:
            position = (METER_WIDTH / 2) + shift
    position = max(0.0, min(float(METER_WIDTH), position))
    full = int(position)
    partial_index = int(round((position - full) * 8))
    if partial_index == 8:
        full += 1
        partial_index = 0
    full = min(full, METER_WIDTH)
    partial = "" if full == METER_WIDTH else PARTIAL_BLOCKS[partial_index]
    used = full + (1 if partial else 0)
    return ("█" * full) + partial + (" " * max(0, METER_WIDTH - used))


def fetch_anu_uint8(length: int) -> list[int]:
    if length < 1 or length > 1024:
        raise QRNGError("length must be between 1 and 1024")
    query = urlencode({"length": length, "type": "uint8"})
    api_key = os.getenv("PYYLMAO_ANU_QRNG_API_KEY", "").strip()
    headers = {"User-Agent": "pyylmao"}
    url = ANU_QRNG_URL
    if api_key:
        url = AQN_QRNG_URL
        headers["x-api-key"] = api_key
    request = Request(f"{url}?{query}", headers=headers)
    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise QRNGError("QRNG request failed")
    data = payload.get("data")
    if not isinstance(data, list):
        raise QRNGError("QRNG response missing data")
    values = [int(item) for item in data]
    if len(values) != length:
        raise QRNGError(f"expected {length} uint8 values, got {len(values)}")
    if any(value < 0 or value > 255 for value in values):
        raise QRNGError("QRNG returned value outside uint8 range")
    return values
