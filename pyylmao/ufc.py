from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard"
ATHLETE_URL = "https://site.web.api.espn.com/apis/common/v3/sports/mma/ufc/athletes/{id}"
NO_EVENTS = "no event IDs... does the regexp need to be updated?"

HELP_LINES = [
    "usage: main.py [-h] [--filter [FILTER ...]] [--fighter [FIGHTER ...]]",
    "               [--prev PREV] [--next NEXT] [--tw TW] [--width WIDTH]",
    "               [--contrast CONTRAST] [--blocks BLOCKS] [--font FONT]",
    "               [--figlet] [--refresh] [--irc] [--numbered] [--ufc]",
    "               [--fightnight] [--contender] [--main]",
    "",
    "Past and upcoming UFC cards with stats and headshots using (full colour) ANSI",
    "or IRC colors",
    "",
    "options:",
    "  -h, --help            show this help message and exit",
    "  --filter [FILTER ...]",
    "                        Only show event names containing filter string (can be",
    "                        specified multiple times, case insensitive)",
    "  --fighter [FIGHTER ...]",
    "                        Only show fighter names containing filter string (can",
    "                        be specified multiple times, case insensitive)",
    "  --prev PREV           Include events from the past N days (default: 7)",
    "  --next NEXT           Include events from the next N days (default: 999)",
    "  --tw TW               Terminal width for layout (default: 80)",
    "  --width WIDTH         Width of the ANSI headshots (default: 24)",
    "  --contrast CONTRAST   img2irc contrast (default: 40)",
    "  --blocks BLOCKS       comma-delimited of unicode block glyph sets to use,",
    '                        set to "all" to use all available (default:',
    "                        eighth,quarter,half,full)",
    "  --font FONT           Font for headings (default: future)",
    "  --figlet              Do not render headshots (default: false)",
    "  --refresh             Refresh event data and ANSI headshot cache (default:",
    "                        false)",
    "  --irc                 Render using IRC formatting (default: false)",
    "  --numbered            Numbered events only (default: false)",
    "  --ufc                 Show UFC events only (default: false)",
    "  --fightnight          Show Fight Night events only (default: false)",
    "  --contender           Show Contender events only (default: false)",
    "  --main                Show main event only (default: false)",
]


@dataclass(frozen=True)
class UFCOptions:
    event_filters: tuple[str, ...] = ()
    fighter_filters: tuple[str, ...] = ()
    prev_days: int = 7
    next_days: int = 999
    terminal_width: int = 80
    image_width: int = 24
    contrast: int = 40
    blocks: str = "eighth,quarter,half,full"
    font: str = "future"
    figlet: bool = False
    refresh: bool = False
    irc: bool = False
    numbered: bool = False
    ufc: bool = False
    fightnight: bool = False
    contender: bool = False
    main: bool = False
    help: bool = False


@dataclass(frozen=True)
class UFCFighter:
    name: str
    country: str = ""
    record: str = ""
    age: str = ""
    height: str = ""
    weight: str = ""
    reach: str = ""
    winner: bool = False
    score: str = ""


@dataclass(frozen=True)
class UFCFight:
    weight_class: str
    date: datetime
    status: str
    fighters: tuple[UFCFighter, UFCFighter]


@dataclass(frozen=True)
class UFCEvent:
    name: str
    date: datetime
    fights: tuple[UFCFight, ...]


class UFCProvider(Protocol):
    def load_events(self, start: datetime, end: datetime, refresh: bool = False) -> tuple[UFCEvent, ...]:
        ...


class UFCCommandError(RuntimeError):
    pass


class ESPNProvider:
    def __init__(self, athlete_details: bool = False):
        self.athlete_details = athlete_details
        self._event_cache: dict[int, tuple[UFCEvent, ...]] = {}
        self._athlete_cache: dict[str, dict[str, object]] = {}

    def load_events(self, start: datetime, end: datetime, refresh: bool = False) -> tuple[UFCEvent, ...]:
        years = range(start.year, end.year + 1)
        events: list[UFCEvent] = []
        for year in years:
            if refresh or year not in self._event_cache:
                self._event_cache[year] = self._fetch_year(year)
            events.extend(self._event_cache[year])
        return tuple(event for event in events if start <= event.date <= end)

    def _fetch_year(self, year: int) -> tuple[UFCEvent, ...]:
        payload = fetch_json(f"{SCOREBOARD_URL}?dates={year}")
        events = payload.get("events", [])
        if not isinstance(events, list):
            return ()
        return tuple(event for raw in events if (event := self._event_from_json(raw)) is not None)

    def _event_from_json(self, raw: object) -> UFCEvent | None:
        if not isinstance(raw, dict):
            return None
        name = str(raw.get("name") or raw.get("shortName") or "").strip()
        date = parse_espn_date(raw.get("date"))
        competitions = raw.get("competitions", [])
        if not name or date is None or not isinstance(competitions, list):
            return None
        fights = [fight for comp in competitions if (fight := self._fight_from_json(comp)) is not None]
        return UFCEvent(name=name, date=date, fights=tuple(fights))

    def _fight_from_json(self, raw: object) -> UFCFight | None:
        if not isinstance(raw, dict):
            return None
        date = parse_espn_date(raw.get("date")) or datetime.now(UTC)
        status = status_from_competition(raw)
        type_data = raw.get("type")
        weight_class = ""
        if isinstance(type_data, dict):
            weight_class = str(type_data.get("abbreviation") or type_data.get("text") or "")
        competitors = raw.get("competitors", [])
        if not isinstance(competitors, list) or len(competitors) < 2:
            return None
        fighters = [fighter for comp in competitors[:2] if (fighter := self._fighter_from_json(comp)) is not None]
        if len(fighters) != 2:
            return None
        return UFCFight(
            weight_class=weight_class,
            date=date,
            status=status,
            fighters=(fighters[0], fighters[1]),
        )

    def _fighter_from_json(self, raw: object) -> UFCFighter | None:
        if not isinstance(raw, dict):
            return None
        athlete = raw.get("athlete", {})
        if not isinstance(athlete, dict):
            athlete = {}
        athlete_id = str(raw.get("id") or athlete.get("id") or "").strip()
        details = self._athlete_details(athlete_id) if athlete_id and self.athlete_details else {}
        name = str(
            details.get("displayName")
            or details.get("fullName")
            or athlete.get("displayName")
            or athlete.get("fullName")
            or ""
        ).strip()
        if not name:
            return None
        return UFCFighter(
            name=name,
            country=country_from(raw, athlete, details),
            record=record_from(raw, details),
            age=string_value(details.get("age")),
            height=string_value(details.get("displayHeight")),
            weight=string_value(details.get("displayWeight")),
            reach=string_value(details.get("displayReach")),
            winner=bool(raw.get("winner")),
            score=score_from(raw),
        )

    def _athlete_details(self, athlete_id: str) -> dict[str, object]:
        if athlete_id not in self._athlete_cache:
            payload = fetch_json(ATHLETE_URL.format(id=athlete_id))
            athlete = payload.get("athlete", {}) if isinstance(payload, dict) else {}
            self._athlete_cache[athlete_id] = athlete if isinstance(athlete, dict) else {}
        return self._athlete_cache[athlete_id]


DEFAULT_PROVIDER = ESPNProvider()


def is_ufc_command(text: str) -> bool:
    return re.match(r"^!ufc(?:\s.*)?$", text.strip(), flags=re.IGNORECASE) is not None


def render_ufc_command(
    text: str,
    provider: UFCProvider | None = None,
    now: datetime | None = None,
) -> list[str]:
    options = parse_ufc_options(text)
    if options.help:
        return HELP_LINES

    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    start = current - timedelta(days=options.prev_days)
    end = current + timedelta(days=options.next_days)
    try:
        events = (provider or DEFAULT_PROVIDER).load_events(start, end, refresh=options.refresh)
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise UFCCommandError(f"UFC fetch failed: {exc}") from exc

    events = tuple(event for event in events if event_matches(event, options))
    if not events:
        return [NO_EVENTS]

    lines: list[str] = []
    for event in events:
        rendered = render_event(event, options)
        if rendered:
            if lines:
                lines.append("")
            lines.extend(rendered)
    return lines or [NO_EVENTS]


def parse_ufc_options(text: str) -> UFCOptions:
    match = re.match(r"^!ufc(?:\s(.*))?$", text.strip(), flags=re.IGNORECASE)
    raw_args = match.group(1).strip() if match else ""
    try:
        tokens = shlex.split(raw_args)
    except ValueError:
        tokens = raw_args.split()

    values: dict[str, object] = {
        "event_filters": [],
        "fighter_filters": [],
        "prev_days": 7,
        "next_days": 999,
        "terminal_width": 80,
        "image_width": 24,
        "contrast": 40,
        "blocks": "eighth,quarter,half,full",
        "font": "future",
        "figlet": False,
        "refresh": False,
        "irc": False,
        "numbered": False,
        "ufc": False,
        "fightnight": False,
        "contender": False,
        "main": False,
        "help": False,
    }
    option_names = {
        "filter",
        "fighter",
        "prev",
        "next",
        "tw",
        "width",
        "contrast",
        "blocks",
        "font",
        "figlet",
        "refresh",
        "irc",
        "numbered",
        "ufc",
        "fightnight",
        "contender",
        "main",
    }
    i = 0
    while i < len(tokens):
        token = tokens[i]
        normalized = token[2:] if token.startswith("--") else token
        normalized = normalized.lower()
        if token in {"-h", "--help"}:
            values["help"] = True
            i += 1
            continue
        if normalized in {"filter", "fighter"}:
            collected, i = collect_option_values(tokens, i + 1, option_names)
            if collected:
                key = "event_filters" if normalized == "filter" else "fighter_filters"
                casted = values[key]
                assert isinstance(casted, list)
                casted.append(" ".join(collected))
            continue
        if normalized in {"prev", "next", "tw", "width", "contrast"}:
            if i + 1 < len(tokens):
                assign_int(values, normalized, tokens[i + 1])
                i += 2
            else:
                i += 1
            continue
        if normalized in {"blocks", "font"}:
            if i + 1 < len(tokens):
                values[normalized] = tokens[i + 1]
                i += 2
            else:
                i += 1
            continue
        if normalized in {"figlet", "refresh", "irc", "numbered", "ufc", "fightnight", "contender", "main"}:
            if not token.startswith("--") and i + 1 < len(tokens) and tokens[i + 1].lower() in {"true", "false"}:
                values[normalized] = tokens[i + 1].lower() == "true"
                i += 2
            else:
                values[normalized] = True
                i += 1
            continue
        i += 1

    return UFCOptions(
        event_filters=tuple(values["event_filters"]),  # type: ignore[arg-type]
        fighter_filters=tuple(values["fighter_filters"]),  # type: ignore[arg-type]
        prev_days=int(values["prev_days"]),
        next_days=int(values["next_days"]),
        terminal_width=int(values["terminal_width"]),
        image_width=int(values["image_width"]),
        contrast=int(values["contrast"]),
        blocks=str(values["blocks"]),
        font=str(values["font"]),
        figlet=bool(values["figlet"]),
        refresh=bool(values["refresh"]),
        irc=bool(values["irc"]),
        numbered=bool(values["numbered"]),
        ufc=bool(values["ufc"]),
        fightnight=bool(values["fightnight"]),
        contender=bool(values["contender"]),
        main=bool(values["main"]),
        help=bool(values["help"]),
    )


def collect_option_values(tokens: list[str], start: int, option_names: set[str]) -> tuple[list[str], int]:
    collected: list[str] = []
    i = start
    while i < len(tokens):
        normalized = tokens[i][2:] if tokens[i].startswith("--") else tokens[i]
        if tokens[i].startswith("--") or normalized.lower() in option_names or tokens[i] == "-h":
            break
        collected.append(tokens[i])
        i += 1
    return collected, i


def assign_int(values: dict[str, object], name: str, value: str) -> None:
    keys = {
        "prev": "prev_days",
        "next": "next_days",
        "tw": "terminal_width",
        "width": "image_width",
        "contrast": "contrast",
    }
    try:
        values[keys[name]] = max(0, int(value))
    except ValueError:
        return


def event_matches(event: UFCEvent, options: UFCOptions) -> bool:
    lowered_name = event.name.lower()
    if options.event_filters and not all(item.lower() in lowered_name for item in options.event_filters):
        return False
    if options.numbered or options.ufc:
        if re.match(r"^ufc\s+\d", event.name, flags=re.IGNORECASE) is None:
            return False
    if options.fightnight and "fight night" not in lowered_name:
        return False
    if options.contender and "contender" not in lowered_name:
        return False
    if options.fighter_filters:
        names = " ".join(fighter.name for fight in event.fights for fighter in fight.fighters).lower()
        if not all(item.lower() in names for item in options.fighter_filters):
            return False
    return True


def render_event(event: UFCEvent, options: UFCOptions) -> list[str]:
    fights = list(event.fights)
    if options.fighter_filters:
        fights = [fight for fight in fights if fight_matches_fighter(fight, options.fighter_filters)]
    if options.main and fights:
        fights = [fights[-1]]
    if not fights:
        return []

    lines: list[str] = []
    lines.extend(figlet(event_number(event.name), options.font, options.terminal_width))
    lines.extend(figlet(event_title(event.name), options.font, options.terminal_width))
    lines.append(format_event_date(event.date))
    for fight in fights:
        lines.append("")
        lines.extend(render_fight(fight))
    return lines


def render_fight(fight: UFCFight) -> list[str]:
    left, right = fight.fighters
    status_left = "WINNER" if left.winner else fight.status
    status_right = "WINNER" if right.winner else fight.status
    labels = [
        ("", left.name, right.name),
        ("", left.country or "N/A", right.country or "N/A"),
        ("RECORD", left.record or "N/A", right.record or "N/A"),
        ("AGE", left.age or "N/A", right.age or "N/A"),
        ("HEIGHT", left.height or "N/A", right.height or "N/A"),
        ("WEIGHT", left.weight or "N/A", right.weight or "N/A"),
        ("REACH", left.reach or "N/A", right.reach or "N/A"),
    ]
    lines = [
        f"┏━━━━━ {status_left[:18].center(18)} ━━━━━┓    ┏━━━━━ {status_right[:18].center(18)} ━━━━━┓"
    ]
    if fight.weight_class:
        lines.append(f"{fight.weight_class} - {format_fight_date(fight.date)}")
    else:
        lines.append(format_fight_date(fight.date))
    for label, left_value, right_value in labels:
        if label:
            lines.append(f"{left_value:>24}    {label:^10}    {right_value:<24}")
        else:
            lines.append(f"{left_value:^24}    {'':10}    {right_value:^24}")
    if left.score or right.score:
        lines.append(f"{left.score or '':>24}    {'SCORE':^10}    {right.score or '':<24}")
    return lines


def fight_matches_fighter(fight: UFCFight, filters: tuple[str, ...]) -> bool:
    names = " ".join(fighter.name for fighter in fight.fighters).lower()
    return all(item.lower() in names for item in filters)


def figlet(text: str, font: str, width: int) -> list[str]:
    if not text:
        return []
    try:
        import pyfiglet

        rendered = pyfiglet.figlet_format(text, font=font, width=max(width, 20)).rstrip("\n")
        return rendered.splitlines()
    except Exception:
        return [text]


def event_number(name: str) -> str:
    match = re.match(r"^(UFC\s+\d+)", name, flags=re.IGNORECASE)
    return match.group(1) if match else ""


def event_title(name: str) -> str:
    if ":" in name:
        return name.split(":", 1)[1].strip()
    return name


def format_event_date(date: datetime) -> str:
    return date.astimezone(UTC).strftime("%A, %B %d @ %-I%p EST")


def format_fight_date(date: datetime) -> str:
    return date.astimezone(UTC).strftime("%b %d, %I:%M %p")


def parse_espn_date(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def status_from_competition(raw: dict[str, object]) -> str:
    status = raw.get("status", {})
    if isinstance(status, dict):
        type_data = status.get("type", {})
        if isinstance(type_data, dict):
            return str(type_data.get("description") or type_data.get("shortDetail") or "Scheduled").upper()
    return "SCHEDULED"


def country_from(raw: dict[str, object], athlete: dict[str, object], details: dict[str, object]) -> str:
    for source in (details, athlete):
        country = source.get("citizenship")
        if isinstance(country, str) and country:
            return country
        flag = source.get("flag")
        if isinstance(flag, dict) and flag.get("alt"):
            return str(flag["alt"])
        country_data = source.get("citizenshipCountry")
        if isinstance(country_data, dict) and country_data.get("abbreviation"):
            return str(country_data["abbreviation"])
    return ""


def record_from(raw: dict[str, object], details: dict[str, object]) -> str:
    records = raw.get("records", [])
    if isinstance(records, list):
        for record in records:
            if isinstance(record, dict) and record.get("summary"):
                return str(record["summary"])
    stats = details.get("statsSummary")
    if isinstance(stats, dict) and isinstance(stats.get("statistics"), list):
        for item in stats["statistics"]:
            if isinstance(item, dict) and item.get("type") == "wins-losses-draws":
                return str(item.get("displayValue") or "")
    return ""


def score_from(raw: dict[str, object]) -> str:
    linescores = raw.get("linescores", [])
    if not isinstance(linescores, list) or not linescores:
        return ""
    first = linescores[0]
    if isinstance(first, dict):
        return str(first.get("displayValue") or "")
    return ""


def string_value(value: object) -> str:
    return "" if value is None else str(value)


def fetch_json(url: str) -> dict[str, object]:
    request = Request(url, headers={"User-Agent": "pyylmao"})
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))
