from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyylmao.config import BotConfig
from pyylmao.irc import IRCBot, event_from_irc_line, format_raw_irc_success, parse_irc_line, parse_prefix
from pyylmao.llm_tools import LLMToolContext, LLMToolRegistry


class IRCParsingTests(unittest.TestCase):
    def test_parse_irc_line_handles_trailing_parameter(self) -> None:
        self.assertEqual(
            parse_irc_line(":alice!u@h PRIVMSG #c :hello world"),
            ("alice!u@h", "PRIVMSG", ["#c", "hello world"]),
        )

    def test_parse_prefix_splits_user_and_host(self) -> None:
        self.assertEqual(parse_prefix("alice!u@h"), ("alice", "u", "h"))
        self.assertEqual(parse_prefix("irc.example.test"), ("irc.example.test", "", ""))

    def test_event_from_join_line_uses_channel_as_text_and_target(self) -> None:
        event = event_from_irc_line(
            ":alice!u@h JOIN #c",
            own_nick="pyylmao_oss",
            joined_channels=("#c",),
        )

        assert event is not None
        self.assertEqual(event.event_type, "join")
        self.assertEqual(event.text, "#c")
        self.assertEqual(event.channel, "#c")
        self.assertEqual(event.target, "#c")
        self.assertEqual(event.nickname, "alice")
        self.assertEqual(event.username, "u")
        self.assertEqual(event.hostname, "h")
        self.assertEqual(event.channels, ("#c",))

    def test_event_from_nick_line_uses_new_nick_as_text(self) -> None:
        event = event_from_irc_line(":alice!u@h NICK :alice_")

        assert event is not None
        self.assertEqual(event.event_type, "nick")
        self.assertEqual(event.text, "alice_")
        self.assertEqual(event.nickname, "alice")
        self.assertEqual(event.channel, "")

    def test_event_from_ctcp_privmsg_is_not_regular_pubmsg(self) -> None:
        event = event_from_irc_line(
            ":alice!u@h PRIVMSG #c :\x01VERSION\x01",
            own_nick="pyylmao_oss",
        )

        assert event is not None
        self.assertEqual(event.event_type, "ctcp")
        self.assertEqual(event.text, "VERSION")
        self.assertEqual(event.channel, "#c")
        self.assertEqual(event.target, "#c")

    def test_private_message_targets_sender_for_replies(self) -> None:
        event = event_from_irc_line(
            ":alice!u@h PRIVMSG pyylmao_oss :ping",
            own_nick="pyylmao_oss",
        )

        assert event is not None
        self.assertEqual(event.event_type, "privmsg")
        self.assertEqual(event.channel, "")
        self.assertEqual(event.target, "alice")

    def test_raw_irc_tool_success_messages_match_logged_friendly_shapes(self) -> None:
        self.assertEqual(format_raw_irc_success("JOIN #bluesky"), "Joined #bluesky")
        self.assertEqual(format_raw_irc_success("PART #superbowl"), "Parted #superbowl")
        self.assertEqual(format_raw_irc_success("PRIVMSG cj :HI!"), "Message sent to cj")
        self.assertEqual(format_raw_irc_success("INVITE alice :#zod"), "Invited alice to #zod")
        self.assertEqual(format_raw_irc_success("NICK aikurd"), "Nickname changed to aikurd")

    def test_irc_client_populates_channel_users_for_llm_tooling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bot = IRCBot(
                BotConfig(
                    nick="pyylmao_oss",
                    channels=["#c"],
                    state_path=Path(tmp) / "state.json",
                    preview_urls=False,
                    respond_to_llm_triggers=False,
                )
            )

            join = event_from_irc_line(
                ":pyylmao_oss!u@h JOIN #c",
                own_nick="pyylmao_oss",
                joined_channels=("#c",),
            )
            assert join is not None
            bot.update_channel_users(join)
            bot.update_names_reply(["pyylmao_oss", "=", "#c", "@alice +bob pyylmao_oss"])

            registry = LLMToolRegistry(bot.state)
            context = LLMToolContext("#c", (), bot.state)
            self.assertEqual(
                registry.execute(context, "get_channel_users", {"channel": "#c"}),
                "pyylmao_oss\nalice\nbob",
            )

            part = event_from_irc_line(":alice!u@h PART #c", own_nick="pyylmao_oss")
            nick = event_from_irc_line(":bob!u@h NICK :robert", own_nick="pyylmao_oss")
            assert part is not None
            assert nick is not None
            bot.update_channel_users(part)
            bot.update_channel_users(nick)

            self.assertEqual(
                registry.execute(context, "get_channel_users", {"channel": "#c"}),
                "pyylmao_oss\nrobert",
            )


if __name__ == "__main__":
    unittest.main()
