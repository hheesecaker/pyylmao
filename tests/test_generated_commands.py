from __future__ import annotations

import contextlib
import io
import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pyylmao.generated_commands import GeneratedCommandStore, MessageEvent
from pyylmao.llm import LLMResult
from pyylmao.state import JsonState


class MessageEventCompatibilityTests(unittest.TestCase):
    def test_top_level_llm_shim_imports_without_generated_loader(self) -> None:
        previous = sys.modules.pop("llm", None)
        try:
            module = importlib.import_module("llm")
            self.assertTrue(module._pyylmao_api)
            self.assertTrue(hasattr(module, "Toolbox"))
            self.assertTrue(hasattr(module, "get_model"))
            self.assertTrue(hasattr(module, "get_tools"))
        finally:
            if previous is not None:
                sys.modules["llm"] = previous
            else:
                sys.modules.pop("llm", None)

    def test_python_irc_style_source_and_arguments_are_available(self) -> None:
        event = MessageEvent(
            event_type="pubmsg",
            text="!summary 24",
            raw_line=":alice!u@h PRIVMSG #c :!summary 24",
            channel="#c",
            nickname="alice",
            username="u",
            hostname="h",
            target="#c",
        )

        self.assertEqual(event.arguments, ("!summary 24",))
        self.assertEqual(event.args, ("!summary 24",))
        self.assertEqual(event.type, "pubmsg")
        self.assertEqual(event.source.nick, "alice")
        self.assertEqual(event.source.user, "u")
        self.assertEqual(event.source.host, "h")
        self.assertEqual(event.source.nickname, "alice")
        self.assertEqual(str(event.source), "alice!u@h")


class GeneratedCommandStoreTests(unittest.TestCase):
    def make_store(self) -> tuple[GeneratedCommandStore, JsonState, tempfile.TemporaryDirectory[str]]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = JsonState(Path(tmp.name) / "state.json")
        return GeneratedCommandStore(state), state, tmp

    def test_routes_logged_entrypoint_shape_and_captures_stdout(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "hello.py"
        path.write_text(
            "\n".join(
                [
                    "pattern = r'^!hello (.+)$'",
                    "def entrypoint(args, channel, nickname, username, hostname):",
                    "    print(f'{nickname}@{channel}: {args[0]}')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"hello": {"path": str(path), "pattern": r"^!hello (.+)$"}}

        command = store.load("hello", state.data["generated_commands"]["hello"])
        assert command is not None
        self.assertEqual(store.handle("~Alice", "#c", "!hello world"), ["Alice@#c: world"])
        self.assertEqual(store.run_with_args(command, ["manual"], "~Alice", "#c"), ["Alice@#c: manual"])
        self.assertIsNone(store.handle("~Alice", "#c", "!nope world"))

    def test_main_callable_is_generated_command_fallback(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "maincmd.py"
        path.write_text(
            "\n".join(
                [
                    "pattern = r'^!main (.+)$'",
                    "def main(args, channel, nickname):",
                    "    print(f'{nickname}@{channel}: {args}')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"maincmd": {"path": str(path), "pattern": r"^!main (.+)$"}}

        self.assertEqual(store.handle("alice", "#c", "!main smoke"), ["alice@#c: smoke"])

    def test_script_style_generated_command_runs_when_no_callable_exists(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "scriptcmd.py"
        path.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "pattern = r'^!script$'",
                    "print('script ok')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"scriptcmd": {"path": str(path), "pattern": r"^!script$"}}

        load_stdout = io.StringIO()
        with contextlib.redirect_stdout(load_stdout):
            result = store.handle("alice", "#c", "!script")

        self.assertEqual(result, ["script ok"])

    def test_digit_leading_generated_command_names_load_and_reload(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "3daudio.py"
        path.write_text(
            "\n".join(
                [
                    "pattern = r'^3daudio\\.html$'",
                    "def entrypoint(args, channel, nickname, username, hostname):",
                    "    print('artifact ready')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"3daudio": {"path": str(path), "pattern": r"^3daudio\.html$"}}

        self.assertEqual(store.handle("alice", "#c", "3daudio.html"), ["artifact ready"])
        self.assertEqual(store.reload("3daudio"), ["reloaded:", "- generated_commands.3daudio"])

    def test_return_value_is_kept_for_compatibility(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "returns.py"
        path.write_text(
            "def entrypoint(args, channel, nickname, username, hostname):\n    return ['a', 'b']\n",
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"returns": {"path": str(path), "pattern": r"^!returns$"}}

        self.assertEqual(store.handle("alice", "#c", "!returns"), ["a", "b"])

    def test_generated_patterns_are_searched_not_only_matched(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "eval_like.py"
        path.write_text(
            "\n".join(
                [
                    r"pattern = r'(?i)\beval\b\s*(.*)'",
                    "def entrypoint(args, channel, nickname, username, hostname):",
                    "    print(args[0])",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"eval_like": {"path": str(path)}}

        self.assertEqual(
            store.handle(
                "pizza2",
                "#bowlcut",
                "grok doesn't like writing commands that only match at the beginning of a line eval 1+2+3",
            ),
            ["1+2+3"],
        )

    def test_toolbox_patterns_are_searched_not_only_matched(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "tool_eval_like.py"
        path.write_text(
            "\n".join(
                [
                    "import llm",
                    "class Tool(llm.Toolbox):",
                    r"    pattern = r'(?i)\beval\b\s*(.*)'",
                    "    def __init__(self, args):",
                    "        self.args = args",
                    "    def _onload(self):",
                    "        print(self.args[0])",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"tool_eval_like": {"path": str(path)}}

        self.assertEqual(
            store.handle("pizza2", "#bowlcut", "that only match at the beginning eval 1+2+3"),
            ["1+2+3"],
        )

    def test_toolbox_class_api_matches_original_command_reference(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "hello_tool.py"
        path.write_text(
            "\n".join(
                [
                    "import llm",
                    "",
                    "class HelloTool(llm.Toolbox):",
                    "    pattern = r'^!hello (.+)$'",
                    "",
                    "    def __init__(self, event, args):",
                    "        self.event = event",
                    "        self.args = args",
                    "",
                    "    def _onload(self):",
                    "        print(f'Hello, {self.args[0]} from {self.event.channel}!')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"hello_tool": {"path": str(path), "pattern": r"^!hello (.+)$"}}

        self.assertEqual(store.handle("alice", "#c", "!hello world"), ["Hello, world from #c!"])

    def test_toolbox_private_context_gets_reply_target_as_channel(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "private_tool.py"
        path.write_text(
            "\n".join(
                [
                    "import llm",
                    "",
                    "class Tool(llm.Toolbox):",
                    "    pattern = r'^!where$'",
                    "    trigger_on = ['pubmsg', 'privmsg']",
                    "    def __init__(self, channel, target):",
                    "        self.channel = channel",
                    "        self.target = target",
                    "    def _onload(self):",
                    "        print(f'{self.channel}|{self.target}')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"private_tool": {"path": str(path), "pattern": r"^!where$"}}

        self.assertEqual(store.handle("alice", "alice", "!where"), ["alice|alice"])

    def test_direct_run_executes_class_only_toolbox_commands(self) -> None:
        store, state, tmp = self.make_store()
        sent: list[list[str]] = []
        store.raw_irc_sender = lambda commands: sent.append(commands) or ""
        path = Path(tmp.name) / "class_only.py"
        path.write_text(
            "\n".join(
                [
                    "import llm",
                    "",
                    "class Tool(llm.Toolbox):",
                    "    pattern = r'^!classonly (.+)$'",
                    "    def __init__(self, args, connection):",
                    "        self.args = args",
                    "        self.connection = connection",
                    "    def _onload(self):",
                    "        print(self.connection.get_nickname())",
                    "        print(self.connection.reactor.server() is self.connection)",
                    "        self.connection.privmsg('#ops', self.args[0])",
                    "        return f'done {self.args[0]}'",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"class_only": {"path": str(path)}}

        command = store.load("class_only", state.data["generated_commands"]["class_only"])
        assert command is not None
        self.assertEqual(store.run_with_args(command, ["smoke"], "pyylmao", "#c"), ["pyylmao", "True", "done smoke"])
        self.assertEqual(sent, [["PRIVMSG #ops :smoke"]])

    def test_toolbox_connection_exposes_state_backed_channel_users(self) -> None:
        store, state, tmp = self.make_store()
        state.data["kvstore"] = {
            "pyylmao": {
                "irc": {
                    "channels": {
                        "#c": {
                            "users": {
                                "alice": {},
                                "@Bob": {"prefixes": "@"},
                                "+carol": {"modes": "v"},
                            }
                        }
                    }
                }
            }
        }
        path = Path(tmp.name) / "channel_users.py"
        path.write_text(
            "\n".join(
                [
                    "import llm",
                    "class Tool(llm.Toolbox):",
                    "    pattern = r'^!users$'",
                    "    def __init__(self, event, connection):",
                    "        self.event = event",
                    "        self.connection = connection",
                    "    def _onload(self):",
                    "        channel = self.connection.channels[self.event.target]",
                    "        print(','.join(channel.users()))",
                    "        print(channel.has_user('bob'))",
                    "        print(','.join(channel.opers()))",
                    "        print(','.join(channel.voiced()))",
                    "        print(self.connection.reactor.channels[self.event.target] is channel)",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"channel_users": {"path": str(path)}}

        self.assertEqual(
            store.handle("alice", "#c", "!users"),
            ["alice,Bob,carol", "True", "Bob", "carol", "True"],
        )

    def test_pmall_style_toolbox_command_can_send_to_channel_users(self) -> None:
        store, state, tmp = self.make_store()
        sent: list[list[str]] = []
        store.raw_irc_sender = lambda commands: sent.append(commands) or ""
        state.data["kvstore"] = {
            "pyylmao": {
                "irc": {
                    "channels": {
                        "#c": {
                            "users": {
                                "pyylmao": {},
                                "alice": {},
                                "bob": {},
                            }
                        }
                    }
                }
            }
        }
        path = Path(tmp.name) / "pmall.py"
        path.write_text(
            "\n".join(
                [
                    "import llm",
                    "class Tool(llm.Toolbox):",
                    "    pattern = r'^!pmall\\s+(.+)$'",
                    "    def __init__(self, args, event, connection):",
                    "        self.args = args",
                    "        self.event = event",
                    "        self.connection = connection",
                    "    def _onload(self):",
                    "        users = self.connection.channels[self.event.target].users()",
                    "        sent = 0",
                    "        for nick in users:",
                    "            if nick.lower() in (self.connection.get_nickname().lower(), self.event.nickname.lower()):",
                    "                continue",
                    "            self.connection.privmsg(nick, self.args[0])",
                    "            sent += 1",
                    "        print(f'PM sent to {sent} users')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"pmall": {"path": str(path)}}

        self.assertEqual(store.handle("alice", "#c", "!pmall smoke"), ["PM sent to 1 users"])
        self.assertEqual(sent, [["PRIVMSG bob :smoke"]])

    def test_toolbox_async_onload_is_awaited_like_original_command_reference(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "async_tool.py"
        path.write_text(
            "\n".join(
                [
                    "import asyncio",
                    "import llm",
                    "",
                    "class AsyncTool(llm.Toolbox):",
                    "    pattern = r'^!async (.+)$'",
                    "    def __init__(self, args):",
                    "        self.args = args",
                    "    async def _onload(self):",
                    "        await asyncio.sleep(0)",
                    "        print(f'async {self.args[0]}')",
                    "        return 'returned'",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"async_tool": {"path": str(path)}}

        self.assertEqual(store.handle("alice", "#c", "!async smoke"), ["async smoke", "returned"])

    def test_toolbox_can_infer_pattern_from_class(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "class_pattern.py"
        path.write_text(
            "import llm\nclass ClassPattern(llm.Toolbox):\n    pattern = r'^!classy$'\n    def _onload(self):\n        print(self.nickname)\n",
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"class_pattern": {"path": str(path)}}

        self.assertEqual(store.handle("~Alice", "#c", "!classy"), ["Alice"])

    def test_toolbox_can_use_python_irc_style_event_fields_from_logged_examples(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "legacy_event.py"
        path.write_text(
            "\n".join(
                [
                    "import llm",
                    "class LegacyEvent(llm.Toolbox):",
                    "    pattern = r'^!echo (.+)$'",
                    "    def __init__(self, event, connection):",
                    "        self.event = event",
                    "        self.connection = connection",
                    "    def _onload(self):",
                    "        nick = self.event.source.nick",
                    "        msg = self.event.arguments[0]",
                    "        self.connection.privmsg(self.event.target, f'{nick}: {msg}')",
                    "        print('queued')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        sent: list[list[str]] = []
        store.raw_irc_sender = lambda commands: sent.append(commands) or ""
        state.data["generated_commands"] = {"legacy_event": {"path": str(path)}}

        self.assertEqual(store.handle("alice", "#c", "!echo hello"), ["queued"])
        self.assertEqual(sent, [["PRIVMSG #c :alice: !echo hello"]])

    def test_logged_python_irc_imports_forward_raw_commands(self) -> None:
        store, state, tmp = self.make_store()
        sent: list[list[str]] = []
        store.raw_irc_sender = lambda commands: sent.append(commands) or ""
        path = Path(tmp.name) / "irccompat.py"
        path.write_text(
            "\n".join(
                [
                    "import irc.bot",
                    "import irc.client",
                    "from irclib import client",
                    "pattern = r'^!irccompat$'",
                    "def entrypoint(args, channel, nickname, username, hostname):",
                    "    reactor = irc.client.Reactor()",
                    "    connection = reactor.server()",
                    "    print(connection.get_nickname())",
                    "    connection.privmsg(channel, 'via client')",
                    "    bot = irc.bot.SingleServerIRCBot([('irc.example', 6667)], 'n', 'real')",
                    "    bot._join_channels(channel)",
                    "    print(client.ServerConnection is irc.client.ServerConnection)",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"irccompat": {"path": str(path)}}

        self.assertEqual(store.handle("alice", "#c", "!irccompat"), ["pyylmao", "True"])
        self.assertEqual(sent, [["PRIVMSG #c :via client"], ["JOIN #c"]])

    def test_python_irc_event_args_alias_and_connection_methods_work(self) -> None:
        store, state, tmp = self.make_store()
        sent: list[list[str]] = []
        store.raw_irc_sender = lambda commands: sent.append(commands) or ""
        path = Path(tmp.name) / "eventargs.py"
        path.write_text(
            "\n".join(
                [
                    "import llm",
                    "class Tool(llm.Toolbox):",
                    "    pattern = r'^!eventargs\\s+(.+)$'",
                    "    def _onload(self):",
                    "        print(self.event.args[0])",
                    "        self.connection.action(self.channel, 'waves')",
                    "        self.connection.ctcp_reply(self.nickname, 'VERSION', 'pyylmao')",
                    "        self.connection.privmsg_many([self.channel, self.nickname], 'fanout')",
                    "        self.connection.ping('server')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"eventargs": {"path": str(path)}}

        self.assertEqual(store.handle("alice", "#c", "!eventargs hello"), ["!eventargs hello"])
        self.assertEqual(
            sent,
            [
                [
                    "PRIVMSG #c :\x01ACTION waves\x01",
                    "NOTICE alice :\x01VERSION pyylmao\x01",
                    "PRIVMSG #c :fanout",
                    "PRIVMSG alice :fanout",
                    "PING server",
                ],
            ],
        )

    def test_toolbox_event_trigger_routes_to_event_channel(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "welcome.py"
        path.write_text(
            "\n".join(
                [
                    "import llm",
                    "class Welcome(llm.Toolbox):",
                    "    pattern = r'^alice$'",
                    "    trigger_on = 'join'",
                    "    match_field = 'nickname'",
                    "    def _onload(self):",
                    "        print(f'Welcome {self.nickname} to {self.channel}')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"welcome": {"path": str(path)}}

        replies = store.handle_event(
            MessageEvent(
                event_type="join",
                text="#c",
                raw_line=":alice!u@h JOIN #c",
                channel="#c",
                nickname="alice",
                username="u",
                hostname="h",
                target="#c",
            )
        )

        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0].target, "#c")
        self.assertEqual(replies[0].lines, ["Welcome alice to #c"])

    def test_toolbox_send_to_routes_global_events(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "nickwatch.py"
        path.write_text(
            "\n".join(
                [
                    "import llm",
                    "class NickWatch(llm.Toolbox):",
                    "    pattern = r'.*NICK.*'",
                    "    trigger_on = 'nick'",
                    "    match_field = 'raw_line'",
                    "    send_to = ['#ops', '#debug']",
                    "    def _onload(self):",
                    "        print(f'{self.event.nickname} -> {self.event.text}')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"nickwatch": {"path": str(path)}}

        replies = store.handle_event(
            MessageEvent(
                event_type="nick",
                text="alice_",
                raw_line=":alice!u@h NICK :alice_",
                channel="",
                nickname="alice",
                username="u",
                hostname="h",
            )
        )

        self.assertEqual(
            [(reply.target, reply.lines) for reply in replies],
            [
                ("#ops", ["alice -> alice_"]),
                ("#debug", ["alice -> alice_"]),
            ],
        )

    def test_toolbox_send_to_all_uses_joined_channels(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "quitwatch.py"
        path.write_text(
            "\n".join(
                [
                    "import llm",
                    "class QuitWatch(llm.Toolbox):",
                    "    pattern = r'.*'",
                    "    trigger_on = 'quit'",
                    "    send_to = 'all'",
                    "    def _onload(self):",
                    "        print(f'{self.nickname} quit: {self.event.text}')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"quitwatch": {"path": str(path)}}

        replies = store.handle_event(
            MessageEvent(
                event_type="quit",
                text="bye",
                raw_line=":alice!u@h QUIT :bye",
                channel="",
                nickname="alice",
                username="u",
                hostname="h",
                channels=("#a", "#b"),
            )
        )

        self.assertEqual([reply.target for reply in replies], ["#a", "#b"])
        self.assertEqual(replies[0].lines, ["alice quit: bye"])

    def test_toolbox_connection_proxy_sends_raw_commands(self) -> None:
        sent: list[list[str]] = []
        store, state, tmp = self.make_store()
        store.raw_irc_sender = lambda commands: sent.append(commands) or ""
        path = Path(tmp.name) / "whois.py"
        path.write_text(
            "\n".join(
                [
                    "import llm",
                    "class Whois(llm.Toolbox):",
                    "    pattern = r'^!whois (.+)$'",
                    "    def __init__(self, args, connection):",
                    "        self.args = args",
                    "        self.connection = connection",
                    "    def _onload(self):",
                    "        self.connection.whois(self.args[0])",
                    "        self.connection.privmsg('#ops', 'checking')",
                    "        print('queued')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"whois": {"path": str(path)}}

        self.assertEqual(store.handle("alice", "#c", "!whois bob"), ["queued"])
        self.assertEqual(sent, [["WHOIS bob", "PRIVMSG #ops :checking"]])

    def test_toolbox_connection_proxy_supports_invite_and_raw_send(self) -> None:
        sent: list[list[str]] = []
        store, state, tmp = self.make_store()
        store.raw_irc_sender = lambda commands: sent.append(commands) or ""
        path = Path(tmp.name) / "raw.py"
        path.write_text(
            "\n".join(
                [
                    "import llm",
                    "class Raw(llm.Toolbox):",
                    "    pattern = r'^!raw$'",
                    "    def __init__(self, connection):",
                    "        self.connection = connection",
                    "    def _onload(self):",
                    "        self.connection.send_raw('JOIN #zod')",
                    "        self.connection.invite('alice', '#zod')",
                    "        print('ok')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"raw": {"path": str(path), "pattern": r"^!raw$"}}

        self.assertEqual(store.handle("bob", "#c", "!raw"), ["ok"])
        self.assertEqual(sent, [["JOIN #zod", "INVITE alice :#zod"]])

    def test_toolbox_connection_proxy_supports_standard_raw_irc_methods(self) -> None:
        sent: list[list[str]] = []
        store, state, tmp = self.make_store()
        store.raw_irc_sender = lambda commands: sent.append(commands) or ""
        path = Path(tmp.name) / "ops.py"
        path.write_text(
            "\n".join(
                [
                    "import llm",
                    "class Ops(llm.Toolbox):",
                    "    pattern = r'^!ops$'",
                    "    def __init__(self, connection):",
                    "        self.connection = connection",
                    "    def _onload(self):",
                    "        self.connection.kick('#c', 'bob', 'bye')",
                    "        self.connection.mode('#c', '+o', 'alice')",
                    "        self.connection.nick('pyylmao_')",
                    "        self.connection.quit('later')",
                    "        print('sent')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"ops": {"path": str(path), "pattern": r"^!ops$"}}

        self.assertEqual(store.handle("alice", "#c", "!ops"), ["sent"])
        self.assertEqual(
            sent,
            [["KICK #c bob :bye", "MODE #c +o alice", "NICK pyylmao_", "QUIT :later"]],
        )

    def test_legacy_generated_commands_get_direct_irc_command_helper(self) -> None:
        sent: list[list[str]] = []
        store, state, tmp = self.make_store()
        store.raw_irc_sender = lambda commands: sent.append(commands) or ""
        path = Path(tmp.name) / "spam.py"
        path.write_text(
            "\n".join(
                [
                    "pattern = r'^!spam$'",
                    "def entrypoint(args, channel, nickname, username, hostname):",
                    "    irc_command('JOIN #superbowl')",
                    "    irc_command('PRIVMSG #superbowl :incog')",
                    "    print('done')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"spam": {"path": str(path), "pattern": r"^!spam$"}}

        self.assertEqual(store.handle("alice", "#c", "!spam"), ["done"])
        self.assertEqual(sent, [["JOIN #superbowl"], ["PRIVMSG #superbowl :incog"]])

    def test_logged_ircbot_import_shape_sends_raw_irc_commands(self) -> None:
        sent: list[list[str]] = []
        store, state, tmp = self.make_store()
        store.raw_irc_sender = lambda commands: sent.append(commands) or ""
        path = Path(tmp.name) / "invite.py"
        path.write_text(
            "\n".join(
                [
                    "from pyylmao.ircbot import bot",
                    "pattern = r'^!invite (\\S+) (\\S+)$'",
                    "def entrypoint(args, channel, nickname, username, hostname):",
                    "    nick, target_channel = args",
                    "    bot.connection.join(target_channel)",
                    "    bot.connection.invite(nick, target_channel)",
                    "    print(f'Invited {nick} to {target_channel}')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"invite": {"path": str(path), "pattern": r"^!invite (\S+) (\S+)$"}}

        self.assertEqual(
            store.handle("alice", "#c", "!invite malcom #bowlcut"),
            ["Invited malcom to #bowlcut"],
        )
        self.assertEqual(sent, [["JOIN #bowlcut"], ["INVITE malcom :#bowlcut"]])

    def test_older_run_bot_channel_sender_args_api_is_supported(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "yolo.py"
        path.write_text(
            "\n".join(
                [
                    "def run(bot, channel, sender, args):",
                    "    print(f'{sender}@{channel}: yolo')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"yolo": {"path": str(path), "pattern": r"^!yolo$"}}

        self.assertEqual(store.handle("alice", "#c", "!yolo"), ["alice@#c: yolo"])

    def test_command_callable_receives_argument_text(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "random.py"
        path.write_text(
            "\n".join(
                [
                    "def random_command(bot, args):",
                    "    return args.strip() or 'empty'",
                    "",
                    "command = random_command",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"random": {"path": str(path), "pattern": r"^\.random\s*(.*)$"}}

        self.assertEqual(store.handle("alice", "#c", ".random 1 10"), ["1 10"])

    def test_traceback_is_rendered_like_logged_command_failures(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "broken.py"
        path.write_text(
            "def entrypoint(args, channel, nickname, username, hostname):\n    raise ValueError('bad')\n",
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"broken": {"path": str(path), "pattern": r"^!broken$"}}

        lines = store.handle("alice", "#c", "!broken")
        assert lines is not None
        self.assertTrue(lines[0].startswith("Traceback"))
        self.assertTrue(lines[-1].endswith("ValueError: bad"))

    def test_reload_reloads_single_or_all_generated_commands(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "hello.py"
        path.write_text("def entrypoint(args, channel, nickname, username, hostname):\n    print('hi')\n")
        state.data["generated_commands"] = {"hello": {"path": str(path), "pattern": r"^!hello$"}}

        self.assertEqual(store.reload("hello"), ["reloaded:", "- generated_commands.hello"])
        self.assertEqual(store.reload("hello.py"), ["reloaded:", "- generated_commands.hello"])
        self.assertEqual(store.reload(), ["reloaded:", "- generated_commands.hello"])

    def test_enabled_callback_can_gate_generated_commands(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "hello.py"
        path.write_text("def entrypoint(args, channel, nickname, username, hostname):\n    print('hi')\n")
        state.data["generated_commands"] = {"hello": {"path": str(path), "pattern": r"^!hello$"}}

        self.assertIsNone(store.handle("alice", "#c", "!hello", enabled=lambda name: name != "hello"))

    def test_command_entries_feed_cmds_table(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "hello.py"
        path.write_text("pattern = r'^!hello$'\n")
        state.data["generated_commands"] = {"hello": {"path": str(path), "pattern": r"^!hello$"}}

        self.assertEqual(store.command_entries(), (("hello", True, r"^!hello$"),))

    def test_generated_commands_receive_scoped_kv_helper(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "counter.py"
        path.write_text(
            "\n".join(
                [
                    "pattern = r'^!counter$'",
                    "def entrypoint(args, channel, nickname, username, hostname):",
                    "    count = kv.get('count', default=0).expect(int)",
                    "    kv.set('count', count + 1)",
                    "    print(count + 1)",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"counter": {"path": str(path), "pattern": r"^!counter$"}}

        self.assertEqual(store.handle("alice", "#c", "!counter"), ["1"])
        self.assertEqual(store.handle("alice", "#c", "!counter"), ["2"])
        self.assertEqual(state.data["kvstore"]["commands"]["counter"]["count"], 2)

    def test_logged_kv_context_import_shape_uses_configured_state(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "notes.py"
        path.write_text(
            "\n".join(
                [
                    "from pyylmao.kv.backends.sqlite import KvContext",
                    "pattern = r'^!note (.+)$'",
                    "kv = KvContext('commands.notes')",
                    "def entrypoint(args, channel, nickname, username, hostname):",
                    "    kv.append('items', args[0])",
                    "    kv.merge('meta', {'last': args[0], 'seen': {'count': len(kv.get('items').expect(list))}})",
                    "    print(','.join(kv.get('items').expect(list)))",
                    "    print(kv.get('meta.seen.count').expect(int))",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"notes": {"path": str(path), "pattern": r"^!note (.+)$"}}

        self.assertEqual(store.handle("alice", "#c", "!note alpha"), ["alpha", "1"])
        self.assertEqual(store.handle("alice", "#c", "!note beta"), ["alpha,beta", "2"])
        self.assertEqual(state.data["kvstore"]["commands"]["notes"]["items"], ["alpha", "beta"])
        self.assertEqual(state.data["kvstore"]["commands"]["notes"]["meta"], {"last": "beta", "seen": {"count": 2}})

    def test_logged_direct_kv_helper_imports_use_configured_state(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "seen.py"
        path.write_text(
            "\n".join(
                [
                    "from pyylmao.kv import kv_get, kv_set, kv_delete, kv_query, kv_merge",
                    "from pyylmao.kv.backends.sqlite import kv_append",
                    "pattern = r'^!seen (.+)$'",
                    "def entrypoint(args, channel, nickname, username, hostname):",
                    "    kv_set('commands.seen.last', args[0])",
                    "    kv_append('commands.seen.history', args[0])",
                    "    kv_merge('commands.seen.cache', {'latest': {'nick': args[0]}})",
                    "    kv_merge('commands.seen.cache', {'latest': {'channel': channel}})",
                    "    print(kv_get('commands.seen.last'))",
                    "    print(kv_query('commands.seen.history|length'))",
                    "    print(kv_get('commands.seen.cache.latest.channel'))",
                    "    print(kv_delete('commands.seen.missing'))",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"seen": {"path": str(path), "pattern": r"^!seen (.+)$"}}

        self.assertEqual(store.handle("alice", "#c", "!seen bob"), ["bob", "1", "#c", "False"])
        self.assertEqual(store.handle("alice", "#c", "!seen carol"), ["carol", "2", "#c", "False"])
        self.assertEqual(state.data["kvstore"]["commands"]["seen"]["history"], ["bob", "carol"])
        self.assertEqual(
            state.data["kvstore"]["commands"]["seen"]["cache"],
            {"latest": {"nick": "carol", "channel": "#c"}},
        )

    def test_logged_helpers_import_shape_works_in_generated_commands(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "md.py"
        path.write_text(
            "\n".join(
                [
                    "from pyylmao.helpers import md2irc",
                    "pattern = r'^!md (.+)$'",
                    "def entrypoint(args, channel, nickname, username, hostname):",
                    "    print(md2irc(args[0]).decode('utf-8'))",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"md": {"path": str(path), "pattern": r"^!md (.+)$"}}

        self.assertEqual(store.handle("alice", "#c", "!md **hello**"), ["hello"])

    def test_logged_llm_get_model_shape_works_in_generated_commands(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "lllm.py"
        path.write_text(
            "\n".join(
                [
                    "import llm",
                    "pattern = r'^\\.\\.\\. (.+)$'",
                    "def entrypoint(args, channel, nickname, username, hostname):",
                    "    class IrcPoll:",
                    "        question: str",
                    "        options: set[str]",
                    "    model = llm.get_model('openrouter/openai/gpt-oss-120b')",
                    "    response = model.prompt(args[0], schema=IrcPoll)",
                    "    print(response.text())",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"lllm": {"path": str(path), "pattern": r"^\.\.\. (.+)$"}}
        calls: list[tuple[str, str]] = []

        def fake_chat(self, prompt: str, model: str, tools=None, max_tool_rounds: int = 8, **_) -> LLMResult:
            del self, tools, max_tool_rounds
            calls.append((prompt, model))
            return LLMResult(["ok"], 0.0, None, None, model)

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}), patch(
            "pyylmao.llm.OpenRouterClient.chat",
            fake_chat,
        ):
            self.assertEqual(store.handle("alice", "#c", "... make a poll"), ["ok"])

        self.assertEqual(calls[0][1], "openai/gpt-oss-120b")
        self.assertIn("make a poll", calls[0][0])
        self.assertIn("IrcPoll", calls[0][0])

    def test_logged_llm_model_alias_works_in_generated_commands(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "llm_alias.py"
        path.write_text(
            "\n".join(
                [
                    "import llm",
                    "pattern = r'^!llmalias (.+)$'",
                    "def entrypoint(args, channel, nickname, username, hostname):",
                    "    response = llm.model('openrouter/openai/gpt-oss-120b').prompt(args[0])",
                    "    print(response.text())",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"llm_alias": {"path": str(path), "pattern": r"^!llmalias (.+)$"}}
        calls: list[tuple[str, str]] = []

        def fake_chat(self, prompt: str, model: str, tools=None, max_tool_rounds: int = 8, **_) -> LLMResult:
            del self, tools, max_tool_rounds
            calls.append((prompt, model))
            return LLMResult(["ok alias"], 0.0, None, None, model)

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}), patch(
            "pyylmao.llm.OpenRouterClient.chat",
            fake_chat,
        ):
            self.assertEqual(store.handle("alice", "#c", "!llmalias hello"), ["ok alias"])

        self.assertEqual(calls, [("hello", "openai/gpt-oss-120b")])

    def test_logged_llm_prompt_options_work_in_generated_commands(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "judge.py"
        path.write_text(
            "\n".join(
                [
                    "import llm",
                    "pattern = r'^!judge (.+)$'",
                    "def entrypoint(args, channel, nickname, username, hostname):",
                    "    model = llm.get_model('openrouter/x-ai/grok-4.1-fast')",
                    "    response = model.prompt(",
                    "        args[0],",
                    "        system='You are terse',",
                    "        options={'temperature': 0.2},",
                    "    )",
                    "    print(response.text())",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"judge": {"path": str(path), "pattern": r"^!judge (.+)$"}}
        calls = []

        def fake_chat(
            self,
            prompt: str,
            model: str,
            tools=None,
            temperature: float | None = None,
            extra_system: str = "",
            attachments=None,
            **_,
        ) -> LLMResult:
            del self, tools, attachments
            calls.append((prompt, model, temperature, extra_system))
            return LLMResult(["ok"], 0.0, None, None, model)

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}), patch(
            "pyylmao.llm.OpenRouterClient.chat",
            fake_chat,
        ):
            self.assertEqual(store.handle("alice", "#c", "!judge hello"), ["ok"])

        self.assertEqual(calls, [("hello", "x-ai/grok-4.1-fast", 0.2, "You are terse")])

    def test_logged_llm_attachment_shape_works_in_generated_commands(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "imgcap.py"
        path.write_text(
            "\n".join(
                [
                    "import llm",
                    "pattern = r'^!imgcap (https?://\\S+)$'",
                    "def entrypoint(args, channel, nickname, username, hostname):",
                    "    model = llm.get_model('openrouter/openai/gpt-oss-120b')",
                    "    image = llm.Attachment(url=args[0], type='image/png')",
                    "    response = model.prompt('describe image', attachments=[image])",
                    "    print(response.text())",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"imgcap": {"path": str(path), "pattern": r"^!imgcap (https?://\S+)$"}}
        calls = []

        def fake_chat(
            self,
            prompt: str,
            model: str,
            tools=None,
            temperature: float | None = None,
            extra_system: str = "",
            attachments=None,
            **_,
        ) -> LLMResult:
            del self, tools, temperature, extra_system
            calls.append((prompt, model, attachments))
            return LLMResult(["caption"], 0.0, None, None, model)

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}), patch(
            "pyylmao.llm.OpenRouterClient.chat",
            fake_chat,
        ):
            self.assertEqual(store.handle("alice", "#c", "!imgcap https://example.test/a.png"), ["caption"])

        prompt, model, attachments = calls[0]
        self.assertEqual(prompt, "describe image")
        self.assertEqual(model, "openai/gpt-oss-120b")
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].url, "https://example.test/a.png")
        self.assertEqual(attachments[0].type, "image/png")

    def test_logged_llm_get_tools_shape_works_in_generated_commands(self) -> None:
        store, state, tmp = self.make_store()
        state.data["llm_tool_enabled"] = {"run": False, "eval": True}
        path = Path(tmp.name) / "tooldebug.py"
        path.write_text(
            "\n".join(
                [
                    "import llm",
                    "pattern = r'^!tooldebug$'",
                    "def entrypoint(args, channel, nickname, username, hostname):",
                    "    tools = llm.get_tools()",
                    "    print('write_command' in tools)",
                    "    print(tools['write_command'].plugin)",
                    "    print(tools.get('run').enabled)",
                    "    enabled = llm.get_tools(enabled_only=True)",
                    "    print('eval' in enabled)",
                    "    print('run' in enabled)",
                    "    print('save_artifact' in tools)",
                    "    print(tools['read_artifact'].plugin)",
                    "    print(','.join(tool.name for tool in llm.get_tools(['write_command', 'run', 'save_artifact', 'read_artifact'])))",
                    "    print('targetcmd' in llm.get_tools(['targetcmd']))",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        target_path = Path(tmp.name) / "targetcmd.py"
        target_path.write_text(
            "\n".join(
                [
                    "pattern = r'^!target (.+)$'",
                    "def entrypoint(args, channel, nickname, username, hostname):",
                    "    print(f'{nickname}@{channel}: {args[0]}')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {
            "tooldebug": {"path": str(path), "pattern": r"^!tooldebug$"},
            "targetcmd": {"path": str(target_path), "pattern": r"^!target (.+)$"},
        }

        self.assertEqual(
            store.handle("alice", "#c", "!tooldebug"),
            [
                "True",
                "llm_cmd_tools",
                "False",
                "True",
                "False",
                "True",
                "llm_artifact_tools",
                "write_command,run,save_artifact,read_artifact",
                "True",
            ],
        )

    def test_generated_commands_from_llm_get_tools_are_callable(self) -> None:
        store, state, tmp = self.make_store()
        target_path = Path(tmp.name) / "targetcmd.py"
        target_path.write_text(
            "\n".join(
                [
                    "pattern = r'^!target (.+)$'",
                    "def entrypoint(args, channel, nickname, username, hostname):",
                    "    print(f'{nickname}@{channel}: {args[0]}')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        caller_path = Path(tmp.name) / "caller.py"
        caller_path.write_text(
            "\n".join(
                [
                    "import llm",
                    "pattern = r'^!caller$'",
                    "def entrypoint(args, channel, nickname, username, hostname):",
                    "    tool = llm.get_tools(['targetcmd'])['targetcmd']",
                    "    print(tool.plugin)",
                    "    print(tool(args='smoke'))",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {
            "targetcmd": {"path": str(target_path), "pattern": r"^!target (.+)$"},
            "caller": {"path": str(caller_path), "pattern": r"^!caller$"},
        }

        self.assertEqual(
            store.handle("alice", "#c", "!caller"),
            ["pyylmao_generated_commands", "alice@#c: smoke"],
        )

    def test_logged_gpt_tools_imports_bind_to_generated_runtime(self) -> None:
        store, state, tmp = self.make_store()
        path = Path(tmp.name) / "gpttools.py"
        path.write_text(
            "\n".join(
                [
                    "from pyylmao.commands.gpt.tools import (",
                    "    get_enabled_tools,",
                    "    list_artifact,",
                    "    read_artifact,",
                    "    read_command,",
                    "    save_artifact,",
                    ")",
                    "pattern = r'^!gpttools$'",
                    "def entrypoint(args, channel, nickname, username, hostname):",
                    "    print(save_artifact(filename='2/demo.txt', contents='hello', create_dirs='true'))",
                    "    print(read_artifact('2/demo.txt'))",
                    "    print(list_artifact('2'))",
                    "    tools = get_enabled_tools(['read_command', 'run'])",
                    "    print('read_command' in tools)",
                    "    print(tools['read_command'].plugin)",
                    "    print(read_command('ping').splitlines()[0])",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"gpttools": {"path": str(path), "pattern": r"^!gpttools$"}}

        lines = store.handle("alice", "#c", "!gpttools")
        assert lines is not None
        self.assertTrue(lines[0].startswith("━━☛ New artifact: "))
        self.assertEqual(
            lines[1:],
            [
                "hello",
                "2/demo.txt",
                "True",
                "llm_cmd_tools",
                "from __future__ import annotations",
            ],
        )


if __name__ == "__main__":
    unittest.main()
