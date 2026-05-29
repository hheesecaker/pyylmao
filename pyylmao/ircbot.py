from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable


RawIrcSender = Callable[[list[str]], str]

_raw_irc_sender: RawIrcSender | None = None


def set_irc_sender(sender: RawIrcSender | None) -> None:
    global _raw_irc_sender
    _raw_irc_sender = sender


def irc_command(command: str) -> str:
    commands = [line.strip() for line in str(command).splitlines() if line.strip()]
    if not commands:
        return ""
    if _raw_irc_sender is None:
        return "\n".join(f"queued IRC command: {item}" for item in commands)
    return str(_raw_irc_sender(commands))


class ServerConnection:
    def __init__(self) -> None:
        self.reactor = ServerReactorProxy(self)
        self.handlers: list[tuple[str, object, int]] = []
        self.features: dict[str, object] = {}
        self.connected = True
        self.nickname = self.get_nickname()
        self.real_nickname = self.nickname
        self.real_server_name = os.getenv("PYYLMAO_SERVER") or ""
        self.server = self.real_server_name
        self.server_address = self.server
        self.port = int(os.getenv("PYYLMAO_PORT") or "6667")
        self.password = os.getenv("PYYLMAO_PASSWORD")
        self.ircname = os.getenv("PYYLMAO_REALNAME") or self.nickname
        self.buffer = ""
        self.buffer_class = str

    def get_nickname(self) -> str:
        return os.getenv("PYYLMAO_NICK") or "pyylmao"

    def get_server_name(self) -> str:
        return ""

    def is_connected(self) -> bool:
        return True

    def send_raw(self, command: str) -> None:
        irc_command(command)
        return None

    def join(self, channel: str) -> None:
        self.send_raw(f"JOIN {channel}")

    def invite(self, nick: str, channel: str) -> None:
        self.send_raw(f"INVITE {nick} :{channel}")

    def privmsg(self, target: str, text: str) -> None:
        self.send_raw(f"PRIVMSG {target} :{text}")

    def notice(self, target: str, text: str) -> None:
        self.send_raw(f"NOTICE {target} :{text}")

    def part(self, channel: str, message: str = "") -> None:
        suffix = f" :{message}" if message else ""
        self.send_raw(f"PART {channel}{suffix}")

    def kick(self, channel: str, nick: str, comment: str = "") -> None:
        suffix = f" :{comment}" if comment else ""
        self.send_raw(f"KICK {channel} {nick}{suffix}")

    def mode(self, target: str, *args: str) -> None:
        suffix = " ".join(str(arg) for arg in args if str(arg))
        self.send_raw(f"MODE {target}" + (f" {suffix}" if suffix else ""))

    def nick(self, nickname: str) -> None:
        self.send_raw(f"NICK {nickname}")

    def quit(self, message: str = "") -> None:
        self.send_raw("QUIT" + (f" :{message}" if message else ""))

    def disconnect(self, message: str = "") -> None:
        self.quit(message)

    def privmsg_many(self, targets, text: str) -> None:
        for target in normalize_targets(targets):
            self.privmsg(target, text)

    def action(self, target: str, text: str) -> None:
        self.send_raw(f"PRIVMSG {target} :\x01ACTION {text}\x01")

    def ctcp(self, target: str, tag: str, data: str = "") -> None:
        payload = str(tag).upper() + (f" {data}" if data else "")
        self.send_raw(f"PRIVMSG {target} :\x01{payload}\x01")

    def ctcp_reply(self, target: str, tag: str, data: str = "") -> None:
        payload = str(tag).upper() + (f" {data}" if data else "")
        self.send_raw(f"NOTICE {target} :\x01{payload}\x01")

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

    def send_raw_OLD(self, command: str) -> None:
        self.send_raw(command)

    def send_items(self, command: str, *items: str) -> None:
        suffix = " ".join(str(item) for item in items if str(item))
        self.send_raw(str(command).upper() + (f" {suffix}" if suffix else ""))

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


class ServerReactorProxy:
    def __init__(self, connection: ServerConnection) -> None:
        self.connection = connection
        self.connections = [connection]

    def server(self) -> ServerConnection:
        return self.connection

    def process_once(self, timeout: float = 0) -> None:
        del timeout
        return None

    def process_forever(self) -> None:
        return None

    def disconnect_all(self, message: str = "") -> None:
        self.connection.quit(message)


@dataclass
class ServerSpec:
    host: str = ""
    port: int = 6667
    password: str | None = None

    def ensure(self) -> "ServerSpec":
        return self


class PyylmaoIRCBot:
    def __init__(self) -> None:
        self.connection = ServerConnection()
        self.servers = [ServerSpec()]
        self.channels: dict[str, object] = {}
        self.config = {
            "server": os.getenv("PYYLMAO_SERVER") or "",
            "port": int(os.getenv("PYYLMAO_PORT") or "6667"),
            "nickname": self.connection.get_nickname(),
            "channels": [
                item.strip()
                for item in (os.getenv("PYYLMAO_CHANNELS") or "").split(",")
                if item.strip()
            ],
            "enabled": {},
        }
        self.reactor = self.connection.reactor
        self.reactor_class = ServerReactorProxy
        self.dcc_connections: list[object] = []
        self.dcc_manager = None
        self.dcc = None

    def _join_channels(self, channels) -> None:
        if isinstance(channels, str):
            self.connection.join(channels)
            return None
        for channel in channels:
            self.connection.join(str(channel))
        return None

    def connect(self) -> ServerConnection:
        return self.connection

    def start(self) -> None:
        return None

    def die(self, msg: str = "Bye") -> None:
        self.connection.quit(msg)

    def disconnect(self, msg: str = "Bye") -> None:
        self.connection.disconnect(msg)

    def dcc_connect(self, *args, **kwargs) -> None:
        del args, kwargs
        return None

    def dcc_listen(self, *args, **kwargs) -> None:
        del args, kwargs
        return None

    def jump_server(self, *args, **kwargs) -> None:
        del args, kwargs
        return None

    def get_version(self) -> str:
        return "pyylmao ircbot compatibility"


bot = PyylmaoIRCBot()


def normalize_targets(targets) -> list[str]:
    if isinstance(targets, str):
        return [targets]
    try:
        return [str(target) for target in targets]
    except TypeError:
        return [str(targets)]


def register_connection_provider(sender: RawIrcSender | None) -> None:
    set_irc_sender(sender)


def set_irc_sender_from_tool(sender: RawIrcSender | None) -> None:
    set_irc_sender(sender)
