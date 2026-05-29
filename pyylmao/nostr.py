from __future__ import annotations

import html
import json
import re
import ssl
import time
import textwrap
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


NOSTR_COMMAND_RE = re.compile(r"^nostr:(.+)$", re.IGNORECASE | re.DOTALL)
HEX_RE = re.compile(r"^[0-9a-fA-F]{64}$")
BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
DEFAULT_RELAYS = (
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://relay.primal.net",
    "wss://nostr.wine",
    "wss://nostr-pub.wellorder.net",
)


class NostrCommandError(ValueError):
    pass


@dataclass(frozen=True)
class NostrReference:
    raw: str
    event_id: str = ""
    author: str = ""
    relays: tuple[str, ...] = ()
    kind: int | None = None


@dataclass(frozen=True)
class NostrPost:
    event_id: str
    author: str
    content: str
    created_at: int | None = None
    kind: int | None = None
    relays: tuple[str, ...] = ()
    profile: dict[str, Any] = field(default_factory=dict)


def is_nostr_command(text: str) -> bool:
    return bool(NOSTR_COMMAND_RE.match(text.strip()))


def render_nostr_command(
    text: str,
    fetcher: Callable[[NostrReference], NostrPost] | None = None,
    avatar_renderer: Callable[[str], list[str]] | None = None,
) -> list[str]:
    match = NOSTR_COMMAND_RE.match(text.strip())
    if match is None:
        raise NostrCommandError("Usage: nostr:<note|nevent|event-id|npub>")
    reference = parse_nostr_reference(match.group(1).strip())
    post = (fetcher or fetch_nostr_post)(reference)
    return render_nostr_post(post, avatar_renderer=avatar_renderer)


def parse_nostr_reference(value: str) -> NostrReference:
    raw = value.strip()
    while raw.lower().startswith("nostr:"):
        raw = raw[6:].strip()
    if HEX_RE.match(raw):
        return NostrReference(raw=raw, event_id=raw.lower())

    hrp, data = decode_bech32(raw)
    payload = bytes(convertbits(data, 5, 8, False))
    if hrp == "note":
        if len(payload) != 32:
            raise NostrCommandError("Invalid note id")
        return NostrReference(raw=raw, event_id=payload.hex())
    if hrp == "npub":
        if len(payload) != 32:
            raise NostrCommandError("Invalid npub id")
        return NostrReference(raw=raw, author=payload.hex())
    if hrp == "nevent":
        fields = parse_tlv(payload)
        event_values = fields.get(0, ())
        if not event_values or len(event_values[0]) != 32:
            raise NostrCommandError("Invalid nevent id")
        relays = tuple(
            item.decode("utf-8", errors="replace")
            for item in fields.get(1, ())
            if item
        )
        authors = fields.get(2, ())
        kinds = fields.get(3, ())
        kind = int.from_bytes(kinds[0], "big") if kinds else None
        return NostrReference(
            raw=raw,
            event_id=event_values[0].hex(),
            author=authors[0].hex() if authors and len(authors[0]) == 32 else "",
            relays=relays,
            kind=kind,
        )
    if hrp == "nprofile":
        fields = parse_tlv(payload)
        authors = fields.get(0, ())
        if not authors or len(authors[0]) != 32:
            raise NostrCommandError("Invalid nprofile id")
        relays = tuple(
            item.decode("utf-8", errors="replace")
            for item in fields.get(1, ())
            if item
        )
        return NostrReference(raw=raw, author=authors[0].hex(), relays=relays)
    raise NostrCommandError(f"Unsupported Nostr reference: {hrp}")


def fetch_nostr_post(reference: NostrReference, timeout: float = 5.0) -> NostrPost:
    relays = ordered_unique((*reference.relays, *DEFAULT_RELAYS))
    filters: dict[str, Any]
    if reference.event_id:
        filters = {"ids": [reference.event_id], "limit": 1}
    elif reference.author:
        filters = {"authors": [reference.author], "kinds": [1], "limit": 1}
    else:
        raise NostrCommandError("Invalid Nostr reference")

    errors: list[str] = []
    for relay in relays:
        try:
            events = query_relay(relay, filters, timeout=timeout)
        except Exception as exc:
            errors.append(f"{relay}: {exc}")
            continue
        if not events:
            continue
        event = max(events, key=lambda item: int(item.get("created_at") or 0))
        profile = fetch_nostr_profile(str(event.get("pubkey") or ""), relays, timeout=timeout)
        return post_from_event(event, relays=relays, profile=profile)
    if errors:
        raise NostrCommandError(f"Error fetching Nostr event: {errors[0]}")
    raise NostrCommandError("Error fetching Nostr event: not found")


def fetch_nostr_profile(author: str, relays: tuple[str, ...], timeout: float = 3.0) -> dict[str, Any]:
    if not HEX_RE.match(author):
        return {}
    filters = {"authors": [author], "kinds": [0], "limit": 1}
    for relay in relays:
        try:
            events = query_relay(relay, filters, timeout=timeout)
        except Exception:
            continue
        if not events:
            continue
        event = max(events, key=lambda item: int(item.get("created_at") or 0))
        try:
            data = json.loads(str(event.get("content") or "{}"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def query_relay(relay: str, filters: dict[str, Any], timeout: float = 5.0) -> list[dict[str, Any]]:
    try:
        import websocket
    except ModuleNotFoundError as exc:
        raise NostrCommandError("websocket-client is required for Nostr relay fetches") from exc

    sub_id = f"pyylmao-{uuid.uuid4().hex[:12]}"
    events: list[dict[str, Any]] = []
    ws = websocket.create_connection(
        relay,
        timeout=timeout,
        sslopt={"cert_reqs": ssl.CERT_NONE},
        enable_multithread=False,
    )
    try:
        ws.settimeout(timeout)
        ws.send(json.dumps(["REQ", sub_id, filters]))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            message = ws.recv()
            try:
                parsed = json.loads(message)
            except json.JSONDecodeError:
                continue
            if not isinstance(parsed, list) or not parsed:
                continue
            kind = parsed[0]
            if kind == "EVENT" and len(parsed) >= 3 and parsed[1] == sub_id and isinstance(parsed[2], dict):
                events.append(parsed[2])
                if filters.get("ids"):
                    break
            elif kind == "EOSE" and len(parsed) >= 2 and parsed[1] == sub_id:
                break
            elif kind in {"CLOSED", "NOTICE"}:
                break
    finally:
        with contextlib_suppress_all():
            ws.send(json.dumps(["CLOSE", sub_id]))
        with contextlib_suppress_all():
            ws.close()
    return events


def post_from_event(event: dict[str, Any], relays: tuple[str, ...], profile: dict[str, Any]) -> NostrPost:
    return NostrPost(
        event_id=str(event.get("id") or ""),
        author=str(event.get("pubkey") or ""),
        content=clean_content(str(event.get("content") or "")),
        created_at=safe_int(event.get("created_at")),
        kind=safe_int(event.get("kind")),
        relays=relays,
        profile=profile,
    )


def render_nostr_post(
    post: NostrPost,
    avatar_renderer: Callable[[str], list[str]] | None = None,
) -> list[str]:
    display_name = profile_display_name(post)
    username = profile_username(post)
    date = format_created_at(post.created_at)
    header = " ".join(item for item in (display_name, f"@{username}" if username else "", date) if item)
    text_lines = [header]
    for paragraph in (post.content or f"nostr:{post.event_id}").splitlines():
        if not paragraph:
            text_lines.append("")
            continue
        text_lines.extend(
            textwrap.wrap(
                paragraph,
                width=68,
                replace_whitespace=False,
                break_long_words=False,
                break_on_hyphens=False,
            )
            or [""]
        )

    avatar_url = profile_avatar(post)
    avatar_lines = render_avatar_lines(avatar_url, avatar_renderer)
    if not avatar_lines:
        return text_lines
    return merge_avatar_and_text(avatar_lines, text_lines)


def render_avatar_lines(
    avatar_url: str,
    avatar_renderer: Callable[[str], list[str]] | None = None,
) -> list[str]:
    if not avatar_url:
        return []
    renderer = avatar_renderer or default_avatar_renderer
    try:
        return renderer(avatar_url)[:8]
    except Exception:
        return []


def default_avatar_renderer(url: str) -> list[str]:
    from .img2irc import render_img2irc_command

    return render_img2irc_command(f"!img2irc {url} width 10 render irc +blocks")


def merge_avatar_and_text(avatar_lines: list[str], text_lines: list[str]) -> list[str]:
    avatar_width = max((len(strip_irc_codes(line)) for line in avatar_lines), default=0)
    indent = " " * (avatar_width + 2)
    lines: list[str] = []
    for index in range(max(len(avatar_lines), len(text_lines))):
        avatar = avatar_lines[index] if index < len(avatar_lines) else ""
        text = text_lines[index] if index < len(text_lines) else ""
        if avatar and text:
            padding = " " * max(2, avatar_width - len(strip_irc_codes(avatar)) + 2)
            lines.append(f"{avatar}{padding}{text}")
        elif avatar:
            lines.append(avatar)
        elif text:
            lines.append(f"{indent}{text}")
    return lines


def strip_irc_codes(text: str) -> str:
    value = re.sub(r"\x03(?:\d{1,2}(?:,\d{1,2})?)?", "", text)
    return re.sub(r"[\x02\x0f\x16\x1d\x1f]", "", value)


def profile_display_name(post: NostrPost) -> str:
    value = first_profile_text(post.profile, "display_name", "displayName", "name", "username")
    return value or post.author[:12] or "(unknown)"


def profile_username(post: NostrPost) -> str:
    value = first_profile_text(post.profile, "name", "username")
    if value:
        return value.lstrip("@")
    return post.author[:12]


def profile_avatar(post: NostrPost) -> str:
    return first_profile_text(post.profile, "picture", "avatar", "profile_image", "image")


def first_profile_text(profile: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = profile.get(key)
        if value:
            return clean_content(str(value))
    return ""


def format_created_at(value: int | None) -> str:
    if value is None:
        return ""
    try:
        return datetime.fromtimestamp(value, tz=timezone.utc).strftime("%b %d %Y")
    except (OSError, OverflowError, ValueError):
        return str(value)


def clean_content(value: str) -> str:
    text = html.unescape(str(value))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")).strip()


def decode_bech32(value: str) -> tuple[str, list[int]]:
    if not value or value.lower() != value and value.upper() != value:
        raise NostrCommandError("Invalid bech32 casing")
    text = value.lower()
    if any(ord(char) < 33 or ord(char) > 126 for char in text):
        raise NostrCommandError("Invalid bech32 characters")
    separator = text.rfind("1")
    if separator < 1 or separator + 7 > len(text):
        raise NostrCommandError("Invalid bech32 reference")
    hrp = text[:separator]
    data = [BECH32_CHARSET.find(char) for char in text[separator + 1 :]]
    if any(item < 0 for item in data):
        raise NostrCommandError("Invalid bech32 reference")
    if not verify_bech32_checksum(hrp, data) and hrp not in {"note", "nevent", "npub", "nprofile"}:
        raise NostrCommandError("Invalid bech32 checksum")
    return hrp, data[:-6]


def verify_bech32_checksum(hrp: str, data: list[int]) -> bool:
    polymod = bech32_polymod(bech32_hrp_expand(hrp) + data)
    return polymod in {1, 0x2BC830A3}


def bech32_polymod(values: list[int]) -> int:
    generators = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)
    checksum = 1
    for value in values:
        top = checksum >> 25
        checksum = (checksum & 0x1FFFFFF) << 5 ^ value
        for index, generator in enumerate(generators):
            if (top >> index) & 1:
                checksum ^= generator
    return checksum


def bech32_hrp_expand(hrp: str) -> list[int]:
    return [ord(char) >> 5 for char in hrp] + [0] + [ord(char) & 31 for char in hrp]


def convertbits(data: list[int], from_bits: int, to_bits: int, pad: bool = True) -> list[int]:
    accumulator = 0
    bits = 0
    ret: list[int] = []
    maxv = (1 << to_bits) - 1
    max_acc = (1 << (from_bits + to_bits - 1)) - 1
    for value in data:
        if value < 0 or value >> from_bits:
            raise NostrCommandError("Invalid bech32 data")
        accumulator = ((accumulator << from_bits) | value) & max_acc
        bits += from_bits
        while bits >= to_bits:
            bits -= to_bits
            ret.append((accumulator >> bits) & maxv)
    if pad:
        if bits:
            ret.append((accumulator << (to_bits - bits)) & maxv)
    elif bits >= from_bits or ((accumulator << (to_bits - bits)) & maxv):
        raise NostrCommandError("Invalid bech32 padding")
    return ret


def parse_tlv(payload: bytes) -> dict[int, tuple[bytes, ...]]:
    fields: dict[int, list[bytes]] = {}
    index = 0
    while index + 2 <= len(payload):
        field_type = payload[index]
        length = payload[index + 1]
        index += 2
        value = payload[index : index + length]
        if len(value) != length:
            break
        fields.setdefault(field_type, []).append(value)
        index += length
    return {key: tuple(values) for key, values in fields.items()}


def ordered_unique(values: tuple[str, ...]) -> tuple[str, ...]:
    seen = set()
    result = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return tuple(result)


def safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class contextlib_suppress_all:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return True
