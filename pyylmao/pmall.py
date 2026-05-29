from __future__ import annotations

import llm


class Tool(llm.Toolbox):
    pattern = r"^!pmall\s+(.+)$"

    def __init__(self, args, event, connection):
        self.args = args
        self.event = event
        self.connection = connection

    def _onload(self):
        if not self.args or not self.args[0]:
            print("Usage: !pmall <message>")
            return

        message = self.args[0]
        channel = self.event.target

        try:
            from pyylmao.kv.backends.sqlite import default_root
            from pyylmao.history_store import channel_users

            _, state = default_root()
            users = channel_users(state, channel)

            if not users:
                print("No users found in channel")
                return

            my_nick = self.connection.get_nickname()
            sender_nick = self.event.nickname

            sent_count = 0
            for nick in users.keys():
                if nick.lower() not in (my_nick.lower(), sender_nick.lower()):
                    self.connection.privmsg(nick, f"[{sender_nick}] {message}")
                    sent_count += 1

            print(f"PM sent to {sent_count} users")

        except Exception as e:
            print(f"Error: {str(e)}")


def entrypoint(args, channel, nickname, username, hostname):
    del username, hostname
    if not args:
        print("Usage: !pmall <message>")
        return

    message = " ".join(args) if isinstance(args, list) else str(args)
    del message

    try:
        from pyylmao.kv.backends.sqlite import default_root
        from pyylmao.history_store import channel_users

        _, state = default_root()
        users = channel_users(state, channel)

        if not users:
            print("No users found in channel")
            return

        user_list = [nick for nick in users.keys() if nick.lower() != nickname.lower()]
        suffix = "..." if len(user_list) > 10 else ""
        print(f"Would PM {len(user_list)} users: {', '.join(user_list[:10])}{suffix}")

    except Exception as e:
        print(f"Error: {str(e)}")
