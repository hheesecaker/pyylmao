from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyylmao.generated_commands import GeneratedCommandStore
from pyylmao.history_store import add_channel_users
from pyylmao.pmall import Tool
from pyylmao.state import JsonState


class PmallSourceTests(unittest.TestCase):
    def test_reconstructed_toolbox_surface(self) -> None:
        self.assertEqual(Tool.pattern, r"^!pmall\s+(.+)$")

    def test_pmall_style_generated_command_sends_to_channel_users(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = JsonState(Path(tmp.name) / "state.json")
        add_channel_users(state, "#c", ["pyylmao", "alice", "bob"])
        sent: list[list[str]] = []
        source = Path(tmp.name) / "pmall.py"
        source.write_text(
            "import llm\n"
            "class Tool(llm.Toolbox):\n"
            "    pattern = r'^!pmall\\s+(.+)$'\n"
            "    def __init__(self, args, event, connection):\n"
            "        self.args = args\n"
            "        self.event = event\n"
            "        self.connection = connection\n"
            "    def _onload(self):\n"
            "        users = self.connection.channels[self.event.target].users()\n"
            "        sent_count = 0\n"
            "        for nick in users:\n"
            "            if nick.lower() not in (self.connection.get_nickname().lower(), self.event.nickname.lower()):\n"
            "                self.connection.privmsg(nick, f'[{self.event.nickname}] {self.args[0]}')\n"
            "                sent_count += 1\n"
            "        print(f'PM sent to {sent_count} users')\n",
            encoding="utf-8",
        )
        state.data["generated_commands"] = {"pmall": {"path": str(source)}}
        store = GeneratedCommandStore(state, raw_irc_sender=lambda commands: sent.append(commands) or "")

        self.assertEqual(store.handle("alice", "#c", "!pmall smoke"), ["PM sent to 1 users"])
        self.assertEqual(sent, [["PRIVMSG bob :[alice] smoke"]])


if __name__ == "__main__":
    unittest.main()
