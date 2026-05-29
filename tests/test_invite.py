from __future__ import annotations

import unittest

from pyylmao.invite import render_invite_command


class InviteCommandTests(unittest.TestCase):
    def test_invite_sends_raw_irc_and_matches_final_logged_reply(self) -> None:
        sent: list[list[str]] = []

        self.assertEqual(
            render_invite_command(
                "!invite malcom #bowlcut",
                raw_irc_sender=lambda commands: sent.append(commands) or "",
            ),
            ["Invited malcom to #bowlcut"],
        )
        self.assertEqual(sent, [["INVITE malcom :#bowlcut"]])


if __name__ == "__main__":
    unittest.main()
