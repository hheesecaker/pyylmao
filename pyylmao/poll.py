from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .state import JsonState


pattern = r"^(!poll(?:\s+.*)?|\?poll|[a-zA-Z])$"
vote_pattern = r"^\s*([A-Za-z0-9]+)\s*$"

POLL_RE = re.compile(r"^(?:!poll|\?poll)(?:\s+(.*))?$", re.IGNORECASE)
VOTE_RE = re.compile(r"^(?:!vote\s+)?([A-Za-z0-9]+)$", re.IGNORECASE)
LABEL_RE = re.compile(r"(?:^|\s)([A-Za-z0-9]+)\.\s*")
LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


@dataclass(frozen=True)
class PollOption:
    label: str
    text: str


def is_poll_command(text: str) -> bool:
    stripped = text.strip()
    if stripped.lower().startswith("!poll") or stripped == "?poll":
        return True
    if stripped.lower().startswith("!vote"):
        return True
    return bool(re.fullmatch(r"[A-Za-z0-9]", stripped))


class PollStore:
    def __init__(self, state: JsonState):
        self.state = state
        self.root = self.state.data.setdefault("polls", {})

    def handle(self, nickname: str, channel: str, text: str) -> list[str] | None:
        stripped = text.strip()
        lowered = stripped.lower()
        if lowered.startswith("!poll"):
            payload = stripped[5:].strip()
            if payload.lower() in {"stop", "end"}:
                return self.stop(channel, nickname)
            return self.create(channel, nickname, payload)
        if stripped == "?poll":
            return self.show(channel, update=False)
        if lowered.startswith("!vote"):
            choice = stripped[5:].strip()
            return self.vote(channel, nickname, choice)
        if re.fullmatch(r"[A-Za-z0-9]", stripped):
            return self.vote(channel, nickname, stripped)
        return None

    def create(self, channel: str, nickname: str, payload: str) -> list[str]:
        if not payload:
            return [
                f'{nickname}: No options provided. Format: !poll "What to eat? 1. Pizza 2. Tacos" or "A. Pizza B. Tacos"'
            ]
        question, options = parse_poll_payload(payload)
        if len(options) < 2:
            return [
                f'{nickname}: No valid options found. Need 1. 2. A. B. etc. Example: !poll "Favorite food? 1. Pizza 2. Tacos"'
            ]
        data = {
            "question": question,
            "creator": nickname,
            "options": [{"label": option.label, "text": option.text} for option in options],
            "votes": {},
        }
        self.root[channel] = data
        self.state.save()
        labels = [option.label for option in options]
        lines = [f"🗳️ New Poll: {question} started by {nickname}:"]
        lines.extend(f"{option.label}: {option.text}" for option in options)
        lines.append(f"Reply with just {', '.join(labels)} to vote (one per person)! 🗳️")
        return lines

    def stop(self, channel: str, nickname: str) -> list[str]:
        if channel not in self.root:
            return [f"{nickname}: No active poll to stop."]
        del self.root[channel]
        self.state.save()
        return [f"🛑 Poll stopped by {nickname}!"]

    def show(self, channel: str, update: bool = False) -> list[str]:
        poll = self.active(channel)
        if poll is None:
            return ["No active poll in this channel."]
        return render_poll(poll, "📊 Poll Update:" if update else "📊 Current Poll:")

    def vote(self, channel: str, nickname: str, choice: str) -> list[str] | None:
        choice = str(choice).strip().upper()
        if not choice:
            return None
        poll = self.active(channel)
        if poll is None:
            return [f"{nickname}: No active poll in this channel."]
        labels = option_labels(poll)
        if choice not in labels:
            return [f"{nickname}: Invalid option '{choice}'. Valid options: {', '.join(labels)}"]
        poll.setdefault("votes", {})[nickname] = choice
        self.state.save()
        return [f"✅ {nickname} voted {choice}! 🗳️", *render_poll(poll, "📊 Poll Update:")]

    def active(self, channel: str) -> dict[str, Any] | None:
        poll = self.root.get(channel)
        return poll if isinstance(poll, dict) else None


def parse_poll_payload(payload: str) -> tuple[str, list[PollOption]]:
    text = strip_wrapping_quotes(payload.strip())
    labeled = parse_labeled_options(text)
    if labeled:
        return labeled
    flexible = parse_flexible_options(text)
    if flexible:
        return flexible
    return text, []


def parse_labeled_options(text: str) -> tuple[str, list[PollOption]] | None:
    matches = list(LABEL_RE.finditer(text))
    if len(matches) < 2:
        return None
    question = strip_wrapping_quotes(text[: matches[0].start()].strip())
    options: list[PollOption] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        label = match.group(1).upper()
        value = strip_wrapping_quotes(text[start:end].strip())
        if value:
            options.append(PollOption(label, value))
    if len(options) < 2:
        return None
    return question or "Poll", options


def parse_flexible_options(text: str) -> tuple[str, list[PollOption]] | None:
    question = text
    raw_options = ""
    if "?" in text:
        before, after = text.split("?", 1)
        question = before.strip() + "?"
        raw_options = after.strip()
    elif "|" in text:
        before, after = text.split("|", 1)
        question = before.strip()
        raw_options = after.strip()
    if not raw_options:
        return None
    separator = "/" if "/" in raw_options else "|"
    pieces = [strip_wrapping_quotes(item.strip()) for item in raw_options.split(separator)]
    pieces = [item for item in pieces if item]
    if len(pieces) < 2:
        return None
    options = [PollOption(str(index), value) for index, value in enumerate(pieces, start=1)]
    return question or "Poll", options


def render_poll(poll: dict[str, Any], heading: str) -> list[str]:
    lines = [heading]
    question = str(poll.get("question") or "").strip()
    if question:
        lines.append(question)
    counts = vote_counts(poll)
    max_count = max(counts.values(), default=0)
    for option in poll_options(poll):
        count = counts.get(option.label, 0)
        crown = " 👑" if count and count == max_count else ""
        lines.append(f"{option.label}: {option.text}{crown} ({count})")
    lines.append(f"Total votes: {sum(counts.values())}")
    return lines


def poll_options(poll: dict[str, Any]) -> list[PollOption]:
    options = []
    for item in poll.get("options", []):
        if isinstance(item, dict):
            label = str(item.get("label", "")).strip().upper()
            text = str(item.get("text", "")).strip()
            if label and text:
                options.append(PollOption(label, text))
    return options


def option_labels(poll: dict[str, Any]) -> list[str]:
    return [option.label for option in poll_options(poll)]


def vote_counts(poll: dict[str, Any]) -> dict[str, int]:
    counts = {label: 0 for label in option_labels(poll)}
    votes = poll.get("votes", {})
    if isinstance(votes, dict):
        for choice in votes.values():
            label = str(choice).upper()
            if label in counts:
                counts[label] += 1
    return counts


def strip_wrapping_quotes(text: str) -> str:
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1].strip()
    return text.strip()


_generated_store: PollStore | None = None


def entrypoint(args, channel, nickname, username, hostname):
    del username, hostname
    global _generated_store
    if _generated_store is None:
        from pyylmao.kv.backends.sqlite import default_root

        _, state = default_root()
        _generated_store = PollStore(state)
    text = " ".join(str(item) for item in args)
    if text and not text.startswith(("!poll", "?poll", "!vote")) and not re.fullmatch(r"[A-Za-z0-9]", text.strip()):
        text = f"!poll {text}"
    for line in _generated_store.handle(nickname, channel, text) or []:
        print(line)
