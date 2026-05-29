from __future__ import annotations

import re
from typing import Callable

from pyylmao.ircbot import bot


pattern = r"^!invite (\S+) (\S+)$"

RawIrcSender = Callable[[list[str]], str]


def is_invite_command(text: str) -> bool:
    return re.match(pattern, text.strip()) is not None


def render_invite_command(
    text: str,
    raw_irc_sender: RawIrcSender | None = None,
) -> list[str]:
    match = re.match(pattern, text.strip())
    if not match:
        return []
    nick, channel = match.groups()
    send_invite(nick, channel, raw_irc_sender)
    return [f"Invited {nick} to {channel}"]


def entrypoint(args, channel, nickname, username, hostname):
    del channel, nickname, username, hostname
    if len(args) < 2:
        print("Usage: !invite <nick> <channel>")
        return
    nick, target_channel = args[:2]
    bot.connection.invite(nick, target_channel)
    print(f"Invited {nick} to {target_channel}")


def send_invite(
    nick: str,
    channel: str,
    raw_irc_sender: RawIrcSender | None = None,
) -> None:
    if raw_irc_sender is not None:
        raw_irc_sender([f"INVITE {nick} :{channel}"])
        return
    bot.connection.invite(nick, channel)
