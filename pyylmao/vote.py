from __future__ import annotations

from .poll import PollStore
from .state import JsonState


pattern = r"^\s*([A-Za-z0-9]+)\s*$"


def render_vote_command(state: JsonState, nickname: str, channel: str, choice: str) -> list[str] | None:
    return PollStore(state).vote(channel, nickname, choice)


_generated_store: PollStore | None = None


def entrypoint(args, channel, nickname, username, hostname):
    del username, hostname
    global _generated_store
    if _generated_store is None:
        from pyylmao.kv.backends.sqlite import default_root

        _, state = default_root()
        _generated_store = PollStore(state)
    choice = " ".join(str(item) for item in args)
    for line in _generated_store.vote(channel, nickname, choice) or []:
        print(line)
