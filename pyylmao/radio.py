from __future__ import annotations

from .state import JsonState


RADIO_HELP = [
    "!np: Show the current track playing",
    "!next: Show the next track",
    "!skip: Skip to the next track",
    "!queued: List tracks in the queue",
    "!playlist: List tracks in the active playlist",
    "!play <query>: Play the first result",
    "!queue <query>: Add to queue",
    "!search <query>: Search for tracks",
    "!new <name>: Create a new playlist",
    "!switch <name>: Switch the active playlist",
    "!shuffle [name]: Shuffle active or specified playlist",
    "!remove <query>: Remove a track from the playlist",
    "+add <playlist> <link>: Append a track/album/artist/playlist",
]


class RadioStore:
    def __init__(self, state: JsonState):
        self.state = state
        radio = self.state.data.setdefault("radio", {})
        radio.setdefault("queue", [])
        radio.setdefault("playlists", {})

    def handle(self, text: str) -> list[str] | None:
        stripped = text.strip()
        lowered = stripped.lower()
        if lowered == "!queued":
            return self.render_queue()
        if lowered.startswith("!new "):
            name = stripped[5:].strip()
            if not name:
                return ["Usage: !new <name>"]
            return self.create_playlist(name)
        return None

    def render_queue(self) -> list[str]:
        queue = list(self.state.data["radio"]["queue"])
        if not queue:
            return ["Queue is empty."]
        return [f"{index}. {track}" for index, track in enumerate(queue, start=1)]

    def create_playlist(self, name: str) -> list[str]:
        playlists = self.state.data["radio"]["playlists"]
        playlists.setdefault(name, [])
        self.state.save()
        return [f"Playlist  {name}  successfully created!"]


def is_radio_help_command(text: str) -> bool:
    return text.strip().lower() == "!help"


def render_radio_help() -> list[str]:
    return list(RADIO_HELP)
