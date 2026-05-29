from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Callable

from .formatting import clean_nick
from .state import JsonState


REMINDER_COMMANDS = {"!reminder", "!reminders", "!remindme"}
TZ_OFFSETS = {
    "UTC": 0,
    "GMT": 0,
    "EST": -5,
    "EDT": -4,
    "EASTERN": -5,
    "PST": -8,
    "PDT": -7,
    "PACIFIC": -8,
}
MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


@dataclass(frozen=True)
class ParsedReminder:
    text: str
    due_at: datetime


class ReminderStore:
    def __init__(
        self,
        state: JsonState,
        now: Callable[[], datetime] | None = None,
    ):
        self.state = state
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.state.data.setdefault("reminders", [])

    def handle(self, nick: str, target: str, text: str) -> list[str] | None:
        stripped = text.strip()
        parts = stripped.split(maxsplit=1)
        if not parts or parts[0].lower() not in REMINDER_COMMANDS:
            return None
        if len(parts) == 1:
            return self.list()
        parsed = parse_reminder_request(parts[1], self.now())
        if parsed is None:
            return ["Usage: !remindme <message> in <n> seconds|minutes|hours|days"]
        entry = {
            "nick": clean_nick(nick),
            "target": target,
            "reminder": parsed.text,
            "timestamp": int(parsed.due_at.timestamp()),
        }
        self.state.data["reminders"].append(entry)
        self.state.save()
        due_text = parsed.due_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
        return [f"Created reminder '{parsed.text}' for {due_text} 🔔"]

    def pop_due(self, nick: str, target: str) -> list[str]:
        now_ts = int(self.now().timestamp())
        nick = clean_nick(nick)
        keep = []
        due = []
        for item in self.state.data.get("reminders", []):
            try:
                timestamp = int(item.get("timestamp", 0))
            except (TypeError, ValueError):
                timestamp = 0
            same_target = not item.get("target") or item.get("target") == target
            if timestamp and timestamp <= now_ts and item.get("nick") == nick and same_target:
                due.append(f"⏰ Reminder for {nick}: {item.get('reminder', '')}")
            else:
                keep.append(item)
        if due:
            self.state.data["reminders"] = keep
            self.state.save()
        return due

    def list(self) -> list[str]:
        reminders = sorted(
            self.state.data.get("reminders", []),
            key=lambda item: int(item.get("timestamp", 0) or 0),
        )
        if not reminders:
            return ["No reminders found."]
        rows = [["nick", "reminder", "time (GMT)"]]
        for item in reminders:
            timestamp = int(item.get("timestamp", 0) or 0)
            due = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
            rows.append([str(item.get("nick", "")), str(item.get("reminder", "")), due])
        return render_plain_table(rows)


def is_reminder_command(text: str) -> bool:
    parts = text.strip().split(maxsplit=1)
    return bool(parts and parts[0].lower() in REMINDER_COMMANDS)


def parse_reminder_request(raw: str, now: datetime) -> ParsedReminder | None:
    now = now.astimezone(timezone.utc)
    if re.search(r"\bat\s+\d{1,2}(?::\d{2})?\s*([ap]m)?\b", raw, flags=re.IGNORECASE):
        absolute = parse_absolute(raw, now)
        if absolute is not None:
            return absolute
    relative = parse_relative(raw, now)
    if relative is not None:
        return relative
    return parse_absolute(raw, now)


def parse_relative(raw: str, now: datetime) -> ParsedReminder | None:
    match = re.search(
        r"\bin\s+(\d+(?:\.\d+)?)\s+(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|weeks?)\b",
        raw,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    try:
        amount = Decimal(match.group(1))
    except (InvalidOperation, ValueError):
        return None
    unit = match.group(2).lower()
    seconds_per_unit = {
        "second": 1,
        "seconds": 1,
        "sec": 1,
        "secs": 1,
        "minute": 60,
        "minutes": 60,
        "min": 60,
        "mins": 60,
        "hour": 3600,
        "hours": 3600,
        "hr": 3600,
        "hrs": 3600,
        "day": 86400,
        "days": 86400,
        "week": 604800,
        "weeks": 604800,
    }
    delta_seconds = int(amount * seconds_per_unit[unit])
    if delta_seconds <= 0:
        return None
    message = (raw[: match.start()] + raw[match.end() :]).strip(" ,.!:;-")
    if not message:
        message = raw[match.end() :].strip(" ,.!:;-")
    if not message:
        return None
    return ParsedReminder(normalize_reminder_text(message), now + timedelta(seconds=delta_seconds))


def parse_absolute(raw: str, now: datetime) -> ParsedReminder | None:
    time_match = re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*([ap]m)?\b", raw, flags=re.IGNORECASE)
    if not time_match:
        return None
    hour = int(time_match.group(1))
    minute = int(time_match.group(2) or "0")
    ampm = (time_match.group(3) or "").lower()
    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None

    tz_name = parse_timezone(raw[time_match.end() :]) or parse_timezone(raw[: time_match.start()]) or "EST"
    tz = timezone(timedelta(hours=TZ_OFFSETS.get(tz_name, -5)))
    local_now = now.astimezone(tz)
    date = absolute_date(raw, local_now)
    local_due = datetime.combine(date, time(hour=hour, minute=minute), tzinfo=tz)
    if local_due <= local_now and not has_explicit_date(raw):
        local_due += timedelta(days=1)

    message = absolute_message(raw, time_match)
    if not message:
        return None
    return ParsedReminder(normalize_reminder_text(message), local_due.astimezone(timezone.utc))


def absolute_date(raw: str, local_now: datetime) -> datetime.date:
    lowered = raw.lower()
    if "tomorrow" in lowered:
        return (local_now + timedelta(days=1)).date()
    month_match = re.search(
        r"\b(?:on\s+)?([a-zA-Z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?",
        raw,
        flags=re.IGNORECASE,
    )
    if month_match and month_match.group(1).lower() in MONTHS:
        month = MONTHS[month_match.group(1).lower()]
        day = int(month_match.group(2))
        year = int(month_match.group(3) or local_now.year)
        candidate = datetime(year, month, day, tzinfo=local_now.tzinfo).date()
        if candidate < local_now.date() and month_match.group(3) is None:
            candidate = datetime(year + 1, month, day, tzinfo=local_now.tzinfo).date()
        return candidate
    return local_now.date()


def has_explicit_date(raw: str) -> bool:
    lowered = raw.lower()
    return "today" in lowered or "tomorrow" in lowered or any(month in lowered for month in MONTHS)


def parse_timezone(raw: str) -> str | None:
    for name in TZ_OFFSETS:
        if re.search(rf"\b{re.escape(name)}(?:\s+time)?\b", raw, flags=re.IGNORECASE):
            return name
    return None


def absolute_message(raw: str, time_match: re.Match[str]) -> str:
    after_time = raw[time_match.end() :]
    after_to = re.search(r"\bto\s+(.+)$", after_time, flags=re.IGNORECASE)
    if after_to:
        return after_to.group(1).strip(" ,.!:;-")
    before = raw[: time_match.start()]
    before = re.sub(
        r"\b(?:on\s+)?[a-zA-Z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?\b",
        "",
        before,
        flags=re.IGNORECASE,
    )
    before = re.sub(r"\bto\s+", "", before, flags=re.IGNORECASE)
    return before.strip(" ,.!:;-")


def normalize_reminder_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if text.lower().startswith("to "):
        text = text[3:].strip()
    if text:
        text = text[0].upper() + text[1:] if text[:1].islower() else text
    return text


def render_plain_table(rows: list[list[str]]) -> list[str]:
    widths = [0] * len(rows[0])
    for row in rows:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(value))
    return [" | ".join(value.ljust(widths[idx]) for idx, value in enumerate(row)) for row in rows]
