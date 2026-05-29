from __future__ import annotations

from pathlib import Path
from types import ModuleType
import unittest

from pyylmao.config import ASSETS_DIR, BASE_DIR, DATA_DIR, BotConfig, _CONFIG
from pyylmao.generated_commands import Toolbox
from pyylmao import ircbot
from pyylmao.runner import _find_toolbox_class


class CompatImportTests(unittest.TestCase):
    def test_config_exports_logged_base_path_constants(self) -> None:
        self.assertIsInstance(BASE_DIR, Path)
        self.assertIsInstance(ASSETS_DIR, Path)
        self.assertIsInstance(DATA_DIR, Path)
        self.assertTrue(BASE_DIR.is_absolute())
        self.assertIsInstance(_CONFIG, BotConfig)

    def test_runner_finds_toolbox_class(self) -> None:
        module = ModuleType("generated_test")

        class Demo(Toolbox):
            pattern = r"^!demo$"

        module.Demo = Demo

        self.assertIs(_find_toolbox_class(module), Demo)

    def test_runner_returns_none_without_toolbox(self) -> None:
        self.assertIsNone(_find_toolbox_class(ModuleType("empty")))

    def test_logged_python_irc_imports_are_available(self) -> None:
        import irc.bot
        import irc.client
        import irc.strings
        from irclib import client

        sent: list[list[str]] = []
        ircbot.set_irc_sender(lambda commands: sent.append(commands) or "")
        self.addCleanup(lambda: ircbot.set_irc_sender(None))

        reactor = irc.client.Reactor()
        connection = reactor.server()
        connection.nick("pyylmao_test")
        connection.privmsg("#c", "hello")
        connection.action("#c", "waves")
        connection.ctcp_reply("alice", "VERSION", "pyylmao")
        connection.privmsg_many(["#c", "alice"], "fanout")
        connection.ping("server")
        event = irc.client.Event("pubmsg", "alice!u@h", "#c", ["!voice", "bob"])
        self.assertIs(reactor.server(), connection)
        self.assertIs(client.ServerConnection, irc.client.ServerConnection)
        self.assertEqual(event.args, ["!voice", "bob"])
        self.assertEqual(event.source.nick, "alice")
        self.assertEqual(event.source.user, "u")
        self.assertEqual(event.source.host, "h")
        self.assertEqual(irc.strings.lower("{}|^AZ"), "[]\\~az")
        self.assertEqual(
            sent,
            [
                ["NICK pyylmao_test"],
                ["PRIVMSG #c :hello"],
                ["PRIVMSG #c :\x01ACTION waves\x01"],
                ["NOTICE alice :\x01VERSION pyylmao\x01"],
                ["PRIVMSG #c :fanout"],
                ["PRIVMSG alice :fanout"],
                ["PING server"],
            ],
        )

        bot = irc.bot.SingleServerIRCBot([("irc.example", 6667)], "nick", "real")
        self.assertTrue(hasattr(bot, "connection"))
        self.assertIn("nickname", bot.config)
        bot._join_channels("#c")
        self.assertEqual(sent[-1], ["JOIN #c"])

    def test_pyylmao_ircbot_exposes_logged_connection_surface(self) -> None:
        sent: list[list[str]] = []
        ircbot.set_irc_sender(lambda commands: sent.append(commands) or "")
        self.addCleanup(lambda: ircbot.set_irc_sender(None))

        self.assertIsInstance(ircbot.bot.config, dict)
        self.assertIs(ircbot.bot.reactor.server(), ircbot.bot.connection)
        self.assertTrue(ircbot.bot.connection.is_connected())

        ircbot.bot.connection.privmsg_many(["#c", "alice"], "hi")
        ircbot.bot.connection.send_items("WHOIS", "alice")

        self.assertEqual(sent, [["PRIVMSG #c :hi"], ["PRIVMSG alice :hi"], ["WHOIS alice"]])


if __name__ == "__main__":
    unittest.main()
