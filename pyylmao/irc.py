from __future__ import annotations

import argparse
import asyncio
import ssl
import concurrent.futures
from pathlib import Path

from .ascii_art import AsciiArtStore
from .cat import CatFileStore
from .config import BotConfig
from .filters import FilterStore
from .formatting import split_irc_lines
from .generated_commands import MessageEvent
from .history_store import (
    add_channel_users,
    remove_channel_user,
    remove_user_from_all_channels,
    rename_user_in_all_channels,
    set_channel_users,
)
from .llm import OpenRouterClient
from .mdcat import MdCatStore
from .router import Router
from .state import JsonState
from .vtrade import VTrade, YahooPriceProvider


class IRCBot:
    def __init__(self, config: BotConfig):
        self.config = config
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.joined_channels: set[str] = set()
        state = JsonState(config.state_path)
        self.state = state
        llm = OpenRouterClient(config.openrouter_api_key) if config.openrouter_api_key else None
        self.router = Router(
            vtrade=VTrade(state, YahooPriceProvider()),
            filters=FilterStore(state),
            llm_client=llm,
            default_model=config.default_model,
            grok_model=config.grok_model,
            preview_urls_enabled=config.preview_urls,
            llm_triggers_enabled=config.respond_to_llm_triggers,
            max_irc_line=config.max_irc_line,
            ascii_art=AsciiArtStore.default(config.ascii_art_dir),
            cat_renderer=CatFileStore.default(config.cat_dir).render,
            mdcat_renderer=MdCatStore.default(config.mdcat_dir).render,
            bluesky_poll_seconds=config.bluesky_poll_seconds,
            bluesky_search_limit=config.bluesky_search_limit,
            raw_irc_sender=self.send_raw_irc_from_tool,
        )

    async def run(self) -> None:
        self.loop = asyncio.get_running_loop()
        ssl_context = ssl.create_default_context() if self.config.tls else None
        self.reader, self.writer = await asyncio.open_connection(
            self.config.server,
            self.config.port,
            ssl=ssl_context,
        )
        if self.config.password:
            await self.raw(f"PASS {self.config.password}")
        await self.raw(f"NICK {self.config.nick}")
        await self.raw(f"USER {self.config.username} 0 * :{self.config.realname}")

        while True:
            assert self.reader is not None
            raw = await self.reader.readline()
            if not raw:
                raise ConnectionError("IRC connection closed")
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            await self.handle_line(line)

    async def handle_line(self, line: str) -> None:
        if line.startswith("PING "):
            await self.raw("PONG " + line.split(" ", 1)[1])
            return

        prefix, command, params = parse_irc_line(line)
        if command == "001":
            for channel in self.config.channels:
                await self.raw(f"JOIN {channel}")
            return
        if command == "353":
            self.update_names_reply(params)
            return

        event = event_from_irc_line(
            line,
            own_nick=self.config.nick,
            joined_channels=self.current_channels(),
        )
        if event is not None:
            self.update_joined_channels(event)
            self.update_channel_users(event)

        if command == "PRIVMSG" and len(params) >= 2:
            if event is not None and event.event_type == "ctcp":
                await self.router.handle_event(event, self.send_privmsg)
                return
            nick = prefix.split("!", 1)[0]
            target = params[0]
            text = params[1]
            reply_target = nick if target == self.config.nick else target
            await self.router.handle(nick, reply_target, text, self.send_privmsg, event)
            return

        if event is None:
            return
        await self.router.handle_event(event, self.send_privmsg)

    async def send_privmsg(self, target: str, lines: list[str]) -> None:
        for line in lines:
            for part in split_irc_lines(line, self.config.max_irc_line):
                await self.raw(f"PRIVMSG {target} :{part}")
                await asyncio.sleep(self.config.line_delay_seconds)

    async def raw(self, line: str) -> None:
        assert self.writer is not None
        self.writer.write((line + "\r\n").encode("utf-8"))
        await self.writer.drain()

    def send_raw_irc_from_tool(self, commands: list[str]) -> str:
        if self.loop is None or self.writer is None:
            return "\n".join(f"queued IRC command: {item}" for item in commands)
        sent = []
        failed = []
        for command in commands:
            future = asyncio.run_coroutine_threadsafe(self.raw(command), self.loop)
            try:
                future.result(timeout=5)
            except (TimeoutError, concurrent.futures.TimeoutError, OSError, RuntimeError) as exc:
                failed.append(f"failed IRC command: {command}: {exc}")
            else:
                sent.append(format_raw_irc_success(command))
        return "\n".join([*sent, *failed])

    def current_channels(self) -> tuple[str, ...]:
        channels = self.joined_channels or set(self.config.channels)
        return tuple(sorted(channels))

    def update_joined_channels(self, event: MessageEvent) -> None:
        if event.event_type == "join" and event.nickname == self.config.nick and event.channel:
            self.joined_channels.add(event.channel)
        if event.event_type == "part" and event.nickname == self.config.nick and event.channel:
            self.joined_channels.discard(event.channel)
        if event.event_type == "kick" and event.target == self.config.nick and event.channel:
            self.joined_channels.discard(event.channel)

    def update_names_reply(self, params: list[str]) -> None:
        channel_index = next((index for index, item in enumerate(params) if item.startswith("#")), -1)
        if channel_index < 0 or channel_index + 1 >= len(params):
            return
        channel = params[channel_index]
        names = params[channel_index + 1].split()
        add_channel_users(self.state, channel, names)

    def update_channel_users(self, event: MessageEvent) -> None:
        if event.event_type == "join" and event.channel:
            if event.nickname == self.config.nick:
                set_channel_users(self.state, event.channel, [event.nickname])
            else:
                add_channel_users(self.state, event.channel, [event.nickname])
        elif event.event_type == "part" and event.channel:
            if event.nickname == self.config.nick:
                set_channel_users(self.state, event.channel, [])
            else:
                remove_channel_user(self.state, event.channel, event.nickname)
        elif event.event_type == "kick" and event.channel and event.target:
            if event.target == self.config.nick:
                set_channel_users(self.state, event.channel, [])
            else:
                remove_channel_user(self.state, event.channel, event.target)
        elif event.event_type == "quit" and event.nickname:
            remove_user_from_all_channels(self.state, event.nickname)
        elif event.event_type == "nick" and event.nickname and event.text:
            rename_user_in_all_channels(self.state, event.nickname, event.text)


def parse_irc_line(line: str) -> tuple[str, str, list[str]]:
    prefix = ""
    if line.startswith(":"):
        prefix, line = line[1:].split(" ", 1)
    if " :" in line:
        before, trailing = line.split(" :", 1)
        parts = before.split()
        params = parts[1:] + [trailing]
    else:
        parts = line.split()
        params = parts[1:]
    command = parts[0].upper() if parts else ""
    return prefix, command, params


def event_from_irc_line(
    line: str,
    own_nick: str = "",
    joined_channels: tuple[str, ...] = (),
) -> MessageEvent | None:
    prefix, command, params = parse_irc_line(line)
    nick, username, hostname = parse_prefix(prefix)
    channels = tuple(joined_channels)
    if command == "PRIVMSG" and len(params) >= 2:
        target = params[0]
        text = params[1]
        reply_target = nick if target == own_nick else target
        channel = target if target.startswith("#") else ""
        if text.startswith("\x01") and text.endswith("\x01") and len(text) >= 2:
            return MessageEvent(
                event_type="ctcp",
                text=text[1:-1],
                raw_line=line,
                channel=channel,
                nickname=nick,
                username=username,
                hostname=hostname,
                target=reply_target,
                channels=channels,
            )
        return MessageEvent(
            event_type="pubmsg" if channel else "privmsg",
            text=text,
            raw_line=line,
            channel=channel,
            nickname=nick,
            username=username,
            hostname=hostname,
            target=reply_target,
            channels=channels,
        )
    if command == "JOIN" and params:
        channel = params[0]
        return MessageEvent(
            event_type="join",
            text=channel,
            raw_line=line,
            channel=channel,
            nickname=nick,
            username=username,
            hostname=hostname,
            target=channel,
            channels=channels,
        )
    if command == "PART" and params:
        channel = params[0]
        reason = params[1] if len(params) > 1 else ""
        return MessageEvent(
            event_type="part",
            text=reason,
            raw_line=line,
            channel=channel,
            nickname=nick,
            username=username,
            hostname=hostname,
            target=channel,
            channels=channels,
        )
    if command == "QUIT":
        reason = params[0] if params else ""
        return MessageEvent(
            event_type="quit",
            text=reason,
            raw_line=line,
            channel="",
            nickname=nick,
            username=username,
            hostname=hostname,
            channels=channels,
        )
    if command == "NICK" and params:
        return MessageEvent(
            event_type="nick",
            text=params[0],
            raw_line=line,
            channel="",
            nickname=nick,
            username=username,
            hostname=hostname,
            channels=channels,
        )
    if command == "KICK" and len(params) >= 2:
        channel = params[0]
        kicked = params[1]
        reason = params[2] if len(params) > 2 else ""
        return MessageEvent(
            event_type="kick",
            text=reason,
            raw_line=line,
            channel=channel,
            nickname=nick,
            username=username,
            hostname=hostname,
            target=kicked,
            channels=channels,
        )
    if command == "NOTICE" and len(params) >= 2:
        target = params[0]
        channel = target if target.startswith("#") else ""
        return MessageEvent(
            event_type="notice",
            text=params[1],
            raw_line=line,
            channel=channel,
            nickname=nick,
            username=username,
            hostname=hostname,
            target=target,
            channels=channels,
        )
    if command == "INVITE" and len(params) >= 2:
        return MessageEvent(
            event_type="invite",
            text=params[1],
            raw_line=line,
            channel="",
            nickname=nick,
            username=username,
            hostname=hostname,
            target=nick,
            channels=channels,
        )
    return None


def parse_prefix(prefix: str) -> tuple[str, str, str]:
    nick = prefix
    username = ""
    hostname = ""
    if "!" in prefix:
        nick, rest = prefix.split("!", 1)
        if "@" in rest:
            username, hostname = rest.split("@", 1)
        else:
            username = rest
    return nick, username, hostname


def format_raw_irc_success(command: str) -> str:
    raw = str(command).strip()
    if not raw:
        return ""
    verb, _, rest = raw.partition(" ")
    action = verb.upper()
    tokens = rest.split()

    if action == "JOIN" and tokens:
        return f"Joined {tokens[0]}"
    if action == "PART" and tokens:
        return f"Parted {tokens[0]}"
    if action == "PRIVMSG" and tokens:
        return f"Message sent to {tokens[0]}"
    if action == "NOTICE" and tokens:
        return f"Notice sent to {tokens[0]}"
    if action == "INVITE" and len(tokens) >= 2:
        return f"Invited {tokens[0]} to {tokens[1].lstrip(':')}"
    if action == "KICK" and len(tokens) >= 2:
        return f"Kicked {tokens[1]} from {tokens[0]}"
    if action == "NICK" and tokens:
        return f"Nickname changed to {tokens[0]}"
    if action == "WHOIS" and tokens:
        return f"WHOIS request sent for {tokens[0]}"
    if action == "WHO" and tokens:
        return f"WHO request sent for {tokens[0]}"
    if action == "NAMES" and tokens:
        return f"NAMES request sent for {tokens[0]}"
    return raw


async def amain() -> None:
    parser = argparse.ArgumentParser(description="Run the pyylmao IRC bot")
    parser.add_argument("--state", type=Path, help="state JSON path")
    args = parser.parse_args()
    config = BotConfig.from_env()
    if args.state:
        config = BotConfig(**{**config.__dict__, "state_path": args.state})
    bot = IRCBot(config)
    await bot.run()


def main() -> None:
    asyncio.run(amain())
