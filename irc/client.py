from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pyylmao import ircbot


@dataclass(frozen=True)
class EventSource:
    nick: str
    user: str = ""
    host: str = ""

    @property
    def nickname(self) -> str:
        return self.nick

    @property
    def username(self) -> str:
        return self.user

    @property
    def hostname(self) -> str:
        return self.host

    def __str__(self) -> str:
        if self.user or self.host:
            return f"{self.nick}!{self.user}@{self.host}"
        return self.nick


@dataclass
class Event:
    type: str
    source: str | EventSource | None = None
    target: str | None = None
    arguments: list[str] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source, EventSource):
            self.source = parse_source(self.source)
        if self.arguments is None:
            self.arguments = []

    @property
    def args(self) -> list[str]:
        return self.arguments or []


class ServerConnection:
    def __init__(self, server: str = "", reactor: "Reactor | None" = None) -> None:
        self.server = server
        self.reactor = reactor or Reactor()
        self.reactor.connections.append(self)
        self.nickname = ""
        self.real_nickname = ""
        self.real_server_name = server
        self.server_address = server
        self.port = 0
        self.password = None
        self.ircname = ""
        self.connected = False
        self.handlers: list[tuple[str, Any, int]] = []
        self.features: dict[str, Any] = {}
        self.buffer = ""
        self.buffer_class = str

    def connect(
        self,
        server: str,
        port: int,
        nickname: str,
        password: str | None = None,
        username: str | None = None,
        ircname: str | None = None,
        **_: Any,
    ) -> "ServerConnection":
        self.server = server
        self.server_address = server
        self.real_server_name = server
        self.port = port
        self.nickname = nickname
        self.real_nickname = nickname
        self.password = password
        self.ircname = ircname or nickname
        self.connected = True
        if password:
            self.send_raw(f"PASS {password}")
        self.send_raw(f"NICK {nickname}")
        user = username or nickname
        realname = ircname or nickname
        self.send_raw(f"USER {user} 0 * :{realname}")
        return self

    def get_nickname(self) -> str:
        return self.nickname or ircbot.bot.connection.get_nickname()

    def get_server_name(self) -> str:
        return self.real_server_name or self.server

    def is_connected(self) -> bool:
        return self.connected or ircbot.bot.connection.is_connected()

    def send_raw(self, command: str) -> None:
        ircbot.irc_command(command)

    def send_raw_OLD(self, command: str) -> None:
        self.send_raw(command)

    def send_items(self, command: str, *items: str) -> None:
        suffix = " ".join(str(item) for item in items if str(item))
        self.send_raw(str(command).upper() + (f" {suffix}" if suffix else ""))

    def privmsg(self, target: str, text: str) -> None:
        self.send_raw(f"PRIVMSG {target} :{text}")

    def privmsg_many(self, targets, text: str) -> None:
        for target in normalize_targets(targets):
            self.privmsg(target, text)

    def notice(self, target: str, text: str) -> None:
        self.send_raw(f"NOTICE {target} :{text}")

    def action(self, target: str, text: str) -> None:
        self.send_raw(f"PRIVMSG {target} :\x01ACTION {text}\x01")

    def ctcp(self, target: str, tag: str, data: str = "") -> None:
        payload = str(tag).upper() + (f" {data}" if data else "")
        self.send_raw(f"PRIVMSG {target} :\x01{payload}\x01")

    def ctcp_reply(self, target: str, tag: str, data: str = "") -> None:
        payload = str(tag).upper() + (f" {data}" if data else "")
        self.send_raw(f"NOTICE {target} :\x01{payload}\x01")

    def join(self, channel: str) -> None:
        self.send_raw(f"JOIN {channel}")

    def part(self, channel: str, message: str = "") -> None:
        self.send_raw(f"PART {channel}" + (f" :{message}" if message else ""))

    def invite(self, nick: str, channel: str) -> None:
        self.send_raw(f"INVITE {nick} :{channel}")

    def kick(self, channel: str, nick: str, comment: str = "") -> None:
        self.send_raw(f"KICK {channel} {nick}" + (f" :{comment}" if comment else ""))

    def mode(self, target: str, *args: str) -> None:
        suffix = " ".join(str(arg) for arg in args if str(arg))
        self.send_raw(f"MODE {target}" + (f" {suffix}" if suffix else ""))

    def nick(self, nickname: str) -> None:
        self.nickname = nickname
        self.send_raw(f"NICK {nickname}")

    def quit(self, message: str = "") -> None:
        self.connected = False
        self.send_raw("QUIT" + (f" :{message}" if message else ""))

    def disconnect(self, message: str = "") -> None:
        self.quit(message)

    def whois(self, nick: str) -> None:
        self.send_raw(f"WHOIS {nick}")

    def names(self, channels: str = "") -> None:
        self.send_raw("NAMES" + (f" {channels}" if channels else ""))

    def list(self, channels: str = "") -> None:
        self.send_raw("LIST" + (f" {channels}" if channels else ""))

    def topic(self, channel: str, new_topic: str | None = None) -> None:
        self.send_raw(f"TOPIC {channel}" + (f" :{new_topic}" if new_topic is not None else ""))

    def admin(self, server: str = "") -> None:
        self.send_raw("ADMIN" + (f" {server}" if server else ""))

    def info(self, server: str = "") -> None:
        self.send_raw("INFO" + (f" {server}" if server else ""))

    def ison(self, *nicknames: str) -> None:
        self.send_raw("ISON " + " ".join(str(nick) for nick in nicknames))

    def links(self, remote_server: str = "", server_mask: str = "") -> None:
        suffix = " ".join(item for item in [remote_server, server_mask] if item)
        self.send_raw("LINKS" + (f" {suffix}" if suffix else ""))

    def lusers(self, server: str = "") -> None:
        self.send_raw("LUSERS" + (f" {server}" if server else ""))

    def motd(self, server: str = "") -> None:
        self.send_raw("MOTD" + (f" {server}" if server else ""))

    def oper(self, name: str, password: str) -> None:
        self.send_raw(f"OPER {name} {password}")

    def pass_(self, password: str) -> None:
        self.password = password
        self.send_raw(f"PASS {password}")

    def ping(self, target: str, target2: str = "") -> None:
        self.send_raw(f"PING {target}" + (f" {target2}" if target2 else ""))

    def pong(self, target: str, target2: str = "") -> None:
        self.send_raw(f"PONG {target}" + (f" {target2}" if target2 else ""))

    def cap(self, subcommand: str, *args: str) -> None:
        suffix = " ".join(str(item) for item in (subcommand, *args) if str(item))
        self.send_raw(f"CAP {suffix}")

    def add_global_handler(self, event: str, handler, priority: int = 0) -> None:
        self.handlers.append((event, handler, priority))

    def remove_global_handler(self, event: str, handler) -> None:
        self.handlers = [
            item for item in self.handlers if not (item[0] == event and item[1] == handler)
        ]

    def process_data(self) -> None:
        return None

    def close(self) -> None:
        return None

    def reconnect(self) -> None:
        return None

    def set_keepalive(self, interval: int = 60) -> None:
        del interval
        return None

    def sasl_login(self, account: str, password: str) -> None:
        del account, password
        return None

    def encode(self, text: str) -> bytes:
        return str(text).encode("utf-8")

    def globops(self, text: str) -> None:
        self.send_raw(f"GLOBOPS :{text}")

    def as_nick(self, nickname: str):
        connection = self

        class _NickContext:
            def __enter__(self):
                connection.nick(nickname)
                return connection

            def __exit__(self, exc_type, exc, tb):
                del exc_type, exc, tb
                return False

        return _NickContext()


class Reactor:
    def __init__(self) -> None:
        self.connections: list[ServerConnection] = []

    def server(self) -> ServerConnection:
        if self.connections:
            return self.connections[0]
        return ServerConnection(reactor=self)

    def process_once(self, timeout: float = 0) -> None:
        del timeout
        return None

    def process_forever(self) -> None:
        return None

    def disconnect_all(self, message: str = "") -> None:
        for connection in list(self.connections):
            connection.disconnect(message)


def parse_source(source: str | None) -> EventSource:
    if not source:
        return EventSource("")
    nick, user, host = str(source), "", ""
    if "!" in nick:
        nick, rest = nick.split("!", 1)
        if "@" in rest:
            user, host = rest.split("@", 1)
        else:
            user = rest
    return EventSource(nick, user, host)


def normalize_targets(targets) -> list[str]:
    if isinstance(targets, str):
        return [targets]
    try:
        return [str(target) for target in targets]
    except TypeError:
        return [str(targets)]
