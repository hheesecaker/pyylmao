from __future__ import annotations

import ipaddress
import re
import socket
from typing import Protocol


class HostResolver(Protocol):
    def addresses_for(self, host: str) -> list[str]:
        ...

    def names_for(self, address: str) -> list[str]:
        ...


class SocketHostResolver:
    def addresses_for(self, host: str) -> list[str]:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        addresses: list[str] = []
        seen: set[str] = set()
        for info in infos:
            address = str(info[4][0])
            if address not in seen:
                seen.add(address)
                addresses.append(address)
        return addresses

    def names_for(self, address: str) -> list[str]:
        hostname, aliases, _addresses = socket.gethostbyaddr(address)
        return [hostname, *aliases]


DEFAULT_RESOLVER = SocketHostResolver()


def is_host_command(text: str) -> bool:
    return re.match(r"^!host\s+(.+)$", text.strip(), flags=re.IGNORECASE) is not None


def render_host_command(text: str, resolver: HostResolver | None = None) -> list[str]:
    match = re.match(r"^!host\s+(.+)$", text.strip(), flags=re.IGNORECASE)
    if not match:
        return ["Usage: !host <hostname-or-ip>"]
    query = match.group(1).strip()
    if not query:
        return ["Usage: !host <hostname-or-ip>"]

    resolver = resolver or DEFAULT_RESOLVER
    try:
        ipaddress.ip_address(query)
    except ValueError:
        try:
            addresses = resolver.addresses_for(query)
        except OSError as exc:
            return [f"host: {exc}"]
        if not addresses:
            return [f"host: no address found for {query}"]
        return [f"{query} has address:", *addresses]

    try:
        names = resolver.names_for(query)
    except OSError as exc:
        return [f"host: {exc}"]
    if not names:
        return [f"host: no name found for {query}"]
    return [f"{query} has reverse name:", *names]
