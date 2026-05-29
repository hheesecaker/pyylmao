from __future__ import annotations

from collections.abc import Callable


COMMANDS: tuple[tuple[str, bool, str], ...] = (
    ("anagram", True, r"^!anagram ([a-zA-Z]+)\s?(.*)$"),
    ("ansi2irc", True, r"^!(?:ansi2irc|irc2ansi) (https?://\S+)$"),
    ("ascii", True, r"^([!~])ascii (.+)$"),
    ("asynctest", True, r"!async (\d+) (.+)$"),
    ("bluesky", True, r"profile\/([\.a-zA-Z0-9\-_]+)\/post\/([a-z0-9]+)"),
    ("bwatchadd", True, r"^!add (.*)$"),
    ("bwatchdel", True, r"^!del (\d+)$"),
    ("bwatchlist", True, r"^!blist$"),
    ("cat", True, r"^!cat (.+)$"),
    ("chess", True, r"^!chess ?(.*)$"),
    (
        "chkdomain",
        True,
        r"^\?(((?!-))(xn--)?[a-z0-9][a-z0-9-_]{0,61}[a-z0-9]{0,1}\.(xn--)?([a-z0-9\-]{1,61}|[a-z0-9-]{1,30}\.[a-z]{2,}))$",
    ),
    ("clearhistory", True, r"^!clear\s?(.+)?$"),
    ("clone", True, r"^(!voice .+)$"),
    ("cmdlist", True, r"^!cmds$"),
    ("cows", True, r"!cowsay(?:\:(\S+))?\s+(.*)$"),
    ("cp", True, r"^tcl cp (.+)$"),
    ("crt", True, r"^([!?])crt\s+(\S+)$"),
    ("curl", True, r"^!curl (http[^ ]+)(\s?.*)$"),
    ("curl2", True, r"^!curl2 (http[^ ]+)$"),
    ("define", True, r"^!define (.+)$"),
    ("drink", True, r"^!drink$"),
    ("echo", True, r"^!echo (.+?) ?([^ ]+=[^ ]+.*)?$"),
    ("eval", True, r"(?i)\beval\b\s*(.*)"),
    ("figlet", True, r"^!(?:fg|f.glet) (.+?) (.*)$"),
    ("flip", True, r"^!flip$"),
    ("forecast", True, r"^!forecast(\s*.*)$"),
    ("gay", True, r"^!gay (.+)$"),
    ("gaytext", True, r"^!gaytext (.*)$"),
    ("godsays", True, r"^!godsays\s*(\d)*$"),
    ("golem", True, r"^([^ >]+)?> ?(.*)$"),
    ("gpt", True, r"^(@|@@)?([\w\-\./:]+)(?(1)|,)\s*(.*)$"),
    ("hf", True, r"^!hf$"),
    ("host", True, r"^!host +(.+)$"),
    ("horoscope", True, r"^\.horoscope\s?(\w*)$"),
    ("howsblair", True, r"^!blair$"),
    ("howsblair2", True, r"^!blair2"),
    ("iching", True, r"!fortune ?(.*)$"),
    ("imdb", True, r"^!imdb(\d{1,2})?(24)? (.+)$"),
    ("img2irc", True, r"^!img2irc\s+(\S+)(?:\s+(.+))?$"),
    ("imgcap", True, r"^(.*(https?://[^ ]+).*)$"),
    ("imghax", True, r"!hax (.*)"),
    ("imgtool", True, r"^!imgtool\s+(\S+)(?:\s+(.+))?$"),
    ("invite", False, r"^!invite (\S+) (\S+)$"),
    ("ircrag", True, r"^siri(\d+)*, (.+)$"),
    ("kv", True, r"^!kv\s+(?:\+\w+\s+)*(get|set|query|append|del|info|modes)\b.*$"),
    ("lepro", True, r"!light ?([#a-zA-Z ]+)? ?(\d+)?$"),
    ("ligma", True, r"^.*ligma\.pro/@[^/]+/(\d+)\s?(.*)$"),
    ("link_title", True, r"(?i)(https?://\S+)"),
    ("livebench", True, r"^([!?])livebench(?:\s+(.*))?$"),
    ("llm_alias", True, r"^!alias(?:\s+.*)?$"),
    ("llm_prices", True, r"^\$llm (.+)$"),
    ("macros", True, r"^([!\+\-].+)$"),
    ("md2html", True, r"^!md2html (.+)$"),
    ("mdcat", True, r"^!mdcat (.+)$"),
    ("models", True, r"^!models$"),
    ("movzig", True, r"^(?:movzig|pyylmao):?[^\w]+(.+)$"),
    ("nostr", True, r"^nostr:(.+)$"),
    ("palette99", True, r"^!palette99$"),
    ("phenoguessr", True, r"^!pheno(?: (.*))?$"),
    ("ping", True, r"^ping$"),
    ("poll", True, r"^(!poll(?:\s+.*)?|\?poll|[a-zA-Z])$"),
    ("polymarket", True, r"(https:\/\/polymarket\.com\/event\/[^ ]+)"),
    ("qrng", True, r"^!qrng (\d+) (\d+)$"),
    ("radio", True, r"^!(np|play|queued|queue|search|skip|next|help)\s?(.*)$"),
    ("random", True, r"^\.random\s*(.*)$"),
    ("reminders", True, r"^(!reminders?|!remindme)?\s?(.*)$"),
    ("seen", True, r"^!seen (.+)$"),
    ("simplebench", True, r"^!simplebench"),
    ("soprano", True, r"^!tts (.+)$"),
    ("spotify", True, r"spotify.com\/(\w+)\/(\w+)"),
    ("stocks", True, r"^!stock ([a-zA-Z\.]{1,6})\s?(.*)$"),
    ("test", True, r"^!test(.) (\d+)$"),
    ("teste", True, r"^!teste (.+)$"),
    ("todo", True, r"!todo\s*(.*)"),
    ("tools", True, r"^(?:!tools ?(enabled)?|[+-]tools?\s+.+)$"),
    (
        "tts",
        True,
        r"^!(alloy|ash|ballad|coral|echo|fable|onyx|nova|sage|shimmer|verse) (.+?) > (.+)$",
    ),
    ("trivia", True, r"^(.+)$"),
    ("twitter", True, r"(?:twitter|x|xcancel|nitter)\.(?:com|net)/.+?/status/(\d+)"),
    ("ufc", True, r"^!ufc\s?(.*)$"),
    ("urbandict", True, r"^!(?:ud|urban) (.+)$"),
    ("vocoder", True, r"^!vocoder (.+)$"),
    ("vote", True, r"^\s*([A-Za-z0-9]+)\s*$"),
    ("vtrade", True, r"^!vtrades?\s*(.*)$"),
    ("weather", True, r"^!weather(\s*.*)$"),
    ("wsummary", True, r"^!wsummary\s(http[^ ]+)?\s?(.*?)$"),
    (
        "youtube",
        True,
        r"(?:youtu\.?be[\.\w]*\/(?:(\w+)\/)*(?:.+?v=)*)([\w\-_]+)",
    ),
    (
        "ytsummary",
        True,
        r"^!summary\s*(?:https?://)?(?:www\.)?(?:youtube\.com/(?:watch\?v=|shorts/|embed/)|youtu\.be/)?([A-Za-z0-9_-]{11})(?:[^\s]*)?(?:\s+(.+))?$",
    ),
    ("ytsearch", False, r"^!yt (.+)$"),
    ("zscore", True, r"^!z(?:score)?(.*)"),
)


def render_command_table(
    is_enabled: Callable[[str], bool] | None = None,
    extra_commands: tuple[tuple[str, bool, str], ...] = (),
) -> list[str]:
    commands = merge_commands(COMMANDS, extra_commands)
    name_width = max(12, len("Command"), *(len(name) for name, _, _ in commands))
    enabled_width = len("Enabled")
    pattern_width = max(len("Pattern"), *(len(pattern) for _, _, pattern in commands))
    widths = (name_width, enabled_width, pattern_width)

    def border() -> str:
        return "+" + "+".join("-" * (width + 2) for width in widths) + "+"

    def row(name: str, enabled: str, pattern: str) -> str:
        return (
            "| "
            + name.center(name_width)
            + " | "
            + enabled.center(enabled_width)
            + " | "
            + pattern.center(pattern_width)
            + " |"
        )

    lines = ["", border(), row("Command", "Enabled", "Pattern"), border()]
    for name, enabled, pattern in commands:
        current_enabled = is_enabled(name) if is_enabled is not None else enabled
        lines.append(row(name, str(current_enabled), pattern))
    lines.append(border())
    return lines


def merge_commands(
    base_commands: tuple[tuple[str, bool, str], ...],
    extra_commands: tuple[tuple[str, bool, str], ...],
) -> tuple[tuple[str, bool, str], ...]:
    if not extra_commands:
        return base_commands
    by_name = {name: (name, enabled, pattern) for name, enabled, pattern in base_commands}
    for name, enabled, pattern in extra_commands:
        by_name[name] = (name, enabled, pattern)
    base_names = [name for name, _, _ in base_commands]
    extra_names = sorted(name for name, _, _ in extra_commands if name not in base_names)
    return tuple(by_name[name] for name in [*base_names, *extra_names])
