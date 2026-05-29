from __future__ import annotations

from typing import Any

from . import client


class SingleServerIRCBot:
    def __init__(
        self,
        server_list: list[tuple[Any, ...]] | tuple[tuple[Any, ...], ...],
        nickname: str,
        realname: str,
        reconnection_interval: int = 60,
        **_: Any,
    ) -> None:
        self.server_list = list(server_list)
        self.nickname = nickname
        self.realname = realname
        self.reconnection_interval = reconnection_interval
        self.reactor = client.Reactor()
        self.connection = client.ServerConnection(reactor=self.reactor)
        self.channels: dict[str, Any] = {}
        self.servers = self.server_list
        self.config: dict[str, Any] = {
            "server": self.server_list[0][0] if self.server_list else "",
            "port": self.server_list[0][1] if self.server_list and len(self.server_list[0]) > 1 else 6667,
            "nickname": nickname,
            "realname": realname,
            "channels": [],
        }
        self.dcc_connections: list[Any] = []
        self.dcc_manager = None
        self.dcc = None
        self.isupport: dict[str, Any] = {}
        self.reactor_class = client.Reactor
        self.__connect_params = (self.server_list, nickname, realname)

    def _connect(self) -> client.ServerConnection:
        server, port, *rest = self.server_list[0]
        password = rest[0] if rest else None
        return self.connection.connect(
            str(server),
            int(port),
            self.nickname,
            password=password,
            username=self.nickname,
            ircname=self.realname,
        )

    def start(self) -> None:
        self._connect()
        self.reactor.process_forever()

    def connect(self, *args: Any, **kwargs: Any) -> client.ServerConnection:
        del args, kwargs
        return self._connect()

    def die(self, msg: str = "Bye") -> None:
        self.connection.quit(msg)

    def disconnect(self, msg: str = "Bye") -> None:
        self.connection.disconnect(msg)

    def _join_channels(self, channels) -> None:
        if isinstance(channels, str):
            self.connection.join(channels)
            return None
        for channel in channels:
            self.connection.join(str(channel))
        return None

    def _dispatcher(self, connection: client.ServerConnection, event: client.Event) -> None:
        method = getattr(self, f"on_{event.type}", None)
        if callable(method):
            method(connection, event)
        for event_name, handler, _priority in list(connection.handlers):
            if event_name == event.type:
                handler(connection, event)

    def _dcc_disconnect(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs
        return None

    def dcc_connect(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs
        return None

    def dcc_listen(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs
        return None

    def jump_server(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs
        return None

    def get_version(self) -> str:
        return "pyylmao python-irc compatibility"


class Channel(dict):
    pass
