from __future__ import annotations

import socket
import unittest

from pyylmao.host import is_host_command, render_host_command


class FakeResolver:
    def __init__(self):
        self.addresses = {
            "gnaa.africa": [
                "104.21.62.143",
                "172.67.136.168",
                "2606:4700:3030::6815:3e8f",
            ]
        }
        self.names = {"104.21.62.143": ["example.reverse"]}

    def addresses_for(self, host: str) -> list[str]:
        if host not in self.addresses:
            raise socket.gaierror(-2, "Name or service not known")
        return self.addresses[host]

    def names_for(self, address: str) -> list[str]:
        if address not in self.names:
            raise socket.herror(1, "Unknown host")
        return self.names[address]


class HostTests(unittest.TestCase):
    def test_detects_logged_command_pattern(self) -> None:
        self.assertTrue(is_host_command("!host gnaa.africa"))
        self.assertTrue(is_host_command("  !HOST 104.21.62.143  "))
        self.assertFalse(is_host_command("?host gnaa.africa"))
        self.assertFalse(is_host_command("!host"))

    def test_forward_lookup_uses_log_style_newline_output(self) -> None:
        self.assertEqual(
            render_host_command("!host gnaa.africa", FakeResolver()),
            [
                "gnaa.africa has address:",
                "104.21.62.143",
                "172.67.136.168",
                "2606:4700:3030::6815:3e8f",
            ],
        )

    def test_reverse_lookup(self) -> None:
        self.assertEqual(
            render_host_command("!host 104.21.62.143", FakeResolver()),
            ["104.21.62.143 has reverse name:", "example.reverse"],
        )

    def test_lookup_error_matches_logged_prefix(self) -> None:
        self.assertEqual(
            render_host_command("!host irc.gnaa.africa", FakeResolver()),
            ["host: [Errno -2] Name or service not known"],
        )
