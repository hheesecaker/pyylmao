from __future__ import annotations

import json
import re
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


HOROSCOPE_URL = "https://horoscope-app-api.vercel.app/api/v1/get-horoscope/daily"

ZODIAC_SIGNS = {
    "aries",
    "taurus",
    "gemini",
    "cancer",
    "leo",
    "virgo",
    "libra",
    "scorpio",
    "sagittarius",
    "capricorn",
    "aquarius",
    "pisces",
}


class HoroscopeProvider(Protocol):
    def fetch(self, sign: str) -> str:
        ...


class OnlineHoroscopeProvider:
    def __init__(self, base_url: str = HOROSCOPE_URL):
        self.base_url = base_url

    def fetch(self, sign: str) -> str:
        query = urlencode({"sign": sign.title(), "day": "TODAY"})
        request = Request(f"{self.base_url}?{query}", headers={"User-Agent": "pyylmao/0.1"})
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
        try:
            horoscope = payload["data"]["horoscope"]
        except (KeyError, TypeError) as exc:
            raise HoroscopeError("unexpected horoscope response") from exc
        if not isinstance(horoscope, str) or not horoscope.strip():
            raise HoroscopeError("empty horoscope response")
        return horoscope.strip()


class HoroscopeError(RuntimeError):
    pass


DEFAULT_PROVIDER = OnlineHoroscopeProvider()


def is_horoscope_command(text: str) -> bool:
    return parse_horoscope_sign(text) is not False


def parse_horoscope_sign(text: str) -> str | None | bool:
    match = re.match(r"^\.horoscope\s*(\w*)$", text.strip(), flags=re.IGNORECASE)
    if not match:
        return False
    sign = match.group(1).strip()
    if not sign:
        return None
    return sign.lower()


def render_horoscope_command(
    text: str,
    nick: str,
    provider: HoroscopeProvider | None = None,
) -> list[str]:
    parsed = parse_horoscope_sign(text)
    if parsed is False:
        return []
    if parsed is None or parsed not in ZODIAC_SIGNS:
        return [f"Sorry, {nick}, couldn't fetch the horoscope for {parsed}."]
    try:
        return [(provider or DEFAULT_PROVIDER).fetch(parsed)]
    except (HoroscopeError, HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        return [f"Sorry, {nick}, couldn't fetch the horoscope for {parsed}."]
