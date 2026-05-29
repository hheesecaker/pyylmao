from __future__ import annotations

import json
import math
import random
import re
import shlex
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .config import ASSETS_DIR
from .img2irc import Img2IRCError, render_img2irc_command
from .state import JsonState


pattern = r"^!pheno(?: (.*))?$"
PHENO_RE = re.compile(pattern, re.IGNORECASE)
KM_TO_MI = 0.621371
WIN_DISTANCE_KM = 1500.0
RECENT_PHENO_LIMIT = 20


class PhenoguessrError(ValueError):
    pass


@dataclass(frozen=True)
class Location:
    name: str
    lat: float
    lon: float


@dataclass(frozen=True)
class PhenotypeEntry:
    slug: str
    label: str
    lat: float
    lon: float
    accepted: tuple[str, ...] = ()
    technical: tuple[str, ...] = ()


class LocationResolver(Protocol):
    def resolve(self, query: str) -> Location | None:
        ...


class StaticLocationResolver:
    def __init__(self, locations: dict[str, Location] | None = None):
        self.locations = locations or DEFAULT_LOCATIONS

    def resolve(self, query: str) -> Location | None:
        return self.locations.get(normalize_location_key(query))


class CachedNominatimResolver:
    def __init__(self, state: JsonState, fallback: LocationResolver | None = None):
        self.state = state
        self.fallback = fallback or StaticLocationResolver()
        self.cache = (
            state.data.setdefault("kvstore", {})
            .setdefault("commands", {})
            .setdefault("phenoguessr", {})
            .setdefault("geocode_cache", {})
        )

    def resolve(self, query: str) -> Location | None:
        key = normalize_location_key(query)
        cached = self.cache.get(key)
        if isinstance(cached, dict):
            try:
                return Location(
                    name=str(cached.get("name") or query),
                    lat=float(cached["lat"]),
                    lon=float(cached["lon"]),
                )
            except (KeyError, TypeError, ValueError):
                pass
        fallback = self.fallback.resolve(query)
        if fallback is not None:
            return fallback
        location = resolve_nominatim(query)
        if location is not None:
            self.cache[key] = {"name": location.name, "lat": location.lat, "lon": location.lon}
            self.state.save()
        return location


class PhenoguessrStore:
    def __init__(
        self,
        state: JsonState,
        entries: tuple[PhenotypeEntry, ...] | list[PhenotypeEntry] | None = None,
        resolver: LocationResolver | None = None,
        image_renderer=None,
        asset_dir: Path | None = None,
        rng: random.Random | None = None,
        now=None,
    ):
        self.state = state
        self.root = state.data.setdefault("kvstore", {}).setdefault("commands", {}).setdefault("phenoguessr", {})
        self.entries = tuple(entries or DEFAULT_PHENOTYPES)
        self.entries_by_slug = {entry.slug: entry for entry in self.entries}
        self.resolver = resolver or CachedNominatimResolver(state)
        self.image_renderer = image_renderer or render_img2irc_command
        self.asset_dir = asset_dir or ASSETS_DIR / "phenoguessr"
        self.rng = rng or random.Random()
        self.now = now or time.time

    def handle(
        self,
        nickname: str,
        text: str,
        username: str = "",
        hostname: str = "",
    ) -> list[str] | None:
        match = PHENO_RE.match(text.strip())
        if not match:
            return None
        guess = collapse_spaces(match.group(1) or "")
        if not guess:
            return self.start()
        return self.guess(nickname, guess, username, hostname)

    def start(self) -> list[str]:
        entry = self.choose_entry()
        gender = self.rng.choice(("male", "female"))
        self.root["current_pheno"] = entry.slug
        self.root["current_pheno_label"] = entry.label
        self.root["current_gender"] = gender
        self.root["current_lat"] = entry.lat
        self.root["current_lon"] = entry.lon
        self.root["current_accepted"] = list(entry.accepted)
        self.root["current_technical"] = list(entry.technical)
        self.root["last_guess_time"] = self.now()
        recent = self.root.setdefault("recent_phenos", [])
        if isinstance(recent, list):
            recent.append(entry.slug)
            del recent[:-RECENT_PHENO_LIMIT]
        self.state.save()

        lines = self.render_image(entry.slug, gender)
        lines.append("New phenotype guesser started! Guess the location with !pheno <location>")
        return lines

    def guess(
        self,
        nickname: str,
        guess: str,
        username: str = "",
        hostname: str = "",
    ) -> list[str]:
        current = self.current_entry()
        if current is None:
            return ["No active game. Start one with !pheno"]
        location = self.resolver.resolve(guess)
        if location is None:
            return [f"Could not resolve the location for: '{guess}'"]

        distance = haversine_km(current.lat, current.lon, location.lat, location.lon)
        accepted = {normalize_location_key(value) for value in current.accepted}
        technical = {normalize_location_key(value) for value in current.technical}
        guess_key = normalize_location_key(guess)
        mask = user_mask(nickname, username, hostname)
        self.root["last_guess_time"] = self.now()

        if guess_key in accepted:
            self.record_stats(mask, 5000, correct=True)
            self.clear_current()
            self.state.save()
            return [
                f"{nickname} guessed {guess}! BULLSEYE! Score: 5000 ({format_number(distance)} km away). "
                f"It was {current.label}! They win!"
            ]

        score = score_for_distance(distance)
        if guess_key in technical or (0 < score and distance <= WIN_DISTANCE_KM):
            self.record_stats(mask, score, correct=True)
            self.clear_current()
            self.state.save()
            qualifier = "Technically correct! " if guess_key in technical else ""
            return [
                f"{nickname} guessed {guess}! {qualifier}Score: {score} ({format_number(distance)} km away). "
                f"It was {current.label}! They win!"
            ]

        self.record_stats(mask, 0, correct=False)
        self.state.save()
        return [
            f"{nickname} guessed {guess}. Incorrect! {format_number(distance)} km "
            f"({format_number(distance * KM_TO_MI)} mi) away."
        ]

    def choose_entry(self) -> PhenotypeEntry:
        recent = self.root.get("recent_phenos")
        recent_set = set(str(item) for item in recent) if isinstance(recent, list) else set()
        candidates = [entry for entry in self.entries if entry.slug not in recent_set]
        if not candidates:
            candidates = list(self.entries)
        return self.rng.choice(candidates)

    def current_entry(self) -> PhenotypeEntry | None:
        slug = self.root.get("current_pheno")
        if not isinstance(slug, str) or not slug:
            return None
        fallback = self.entries_by_slug.get(slug)
        label = self.root.get("current_pheno_label")
        try:
            lat = float(self.root.get("current_lat", fallback.lat if fallback else None))
            lon = float(self.root.get("current_lon", fallback.lon if fallback else None))
        except (TypeError, ValueError):
            return fallback
        accepted = tuple(str(item) for item in self.root.get("current_accepted", ()) if str(item))
        technical = tuple(str(item) for item in self.root.get("current_technical", ()) if str(item))
        return PhenotypeEntry(
            slug=slug,
            label=str(label or (fallback.label if fallback else slug)),
            lat=lat,
            lon=lon,
            accepted=accepted or (fallback.accepted if fallback else ()),
            technical=technical or (fallback.technical if fallback else ()),
        )

    def clear_current(self) -> None:
        for key in (
            "current_pheno",
            "current_pheno_label",
            "current_gender",
            "current_lat",
            "current_lon",
            "current_accepted",
            "current_technical",
        ):
            self.root.pop(key, None)

    def record_stats(self, mask: str, score: int, correct: bool) -> None:
        stats = self.root.setdefault("stats", {})
        if not isinstance(stats, dict):
            stats = {}
            self.root["stats"] = stats
        entry = stats.setdefault(mask, {})
        if not isinstance(entry, dict):
            entry = {}
            stats[mask] = entry
        entry["total_score"] = int(entry.get("total_score", 0)) + int(score)
        if correct:
            entry["correct_guesses"] = int(entry.get("correct_guesses", 0)) + 1
            entry.setdefault("incorrect_guesses", 0)
        else:
            entry["incorrect_guesses"] = int(entry.get("incorrect_guesses", 0)) + 1
            entry.setdefault("correct_guesses", 0)

    def render_image(self, slug: str, gender: str) -> list[str]:
        asset = self.find_asset(slug, gender)
        if asset is None:
            return []
        command = self.image_command(asset)
        mode = str(self.root.get("output_mode") or "imghax").strip().lower()
        try:
            return list(self.image_renderer(command))
        except (Img2IRCError, OSError, ValueError) as exc:
            label = "img2irc" if mode == "img2irc" else "imghax"
            return [f"Error with {label}: {exc}"]

    def image_command(self, asset: Path) -> str:
        mode = str(self.root.get("output_mode") or "imghax").strip().lower()
        command = "!img2irc" if mode == "img2irc" else "!hax"
        parts = [command, shlex.quote(str(asset))]
        options = self.root.get("img2irc_args", {})
        if isinstance(options, dict):
            for key, value in options.items():
                if value in (None, "", False):
                    continue
                name = str(key).strip().replace("_", "-")
                if not name:
                    continue
                parts.extend([name, option_value(value)])
        return " ".join(parts)

    def find_asset(self, slug: str, gender: str) -> Path | None:
        for name in (f"{gender}.jpg", f"{gender}.jpeg", f"{gender}.png", "image.jpg", "image.png"):
            candidate = self.asset_dir / slug / name
            if candidate.exists() and candidate.is_file():
                return candidate
        return None


def is_phenoguessr_command(text: str) -> bool:
    return bool(PHENO_RE.match(text.strip()))


def collapse_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def normalize_location_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def option_value(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        return ",".join(str(item) for item in value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"))
    return str(value)


def user_mask(nickname: str, username: str = "", hostname: str = "") -> str:
    if username or hostname:
        return f"{nickname}!{username}@{hostname}"
    return nickname


def score_for_distance(distance_km: float) -> int:
    if distance_km <= 0:
        return 5000
    if distance_km >= WIN_DISTANCE_KM:
        return 0
    return max(1, min(4999, round(5000 * (1 - distance_km / WIN_DISTANCE_KM) ** 1.5)))


def format_number(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text or "0"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def resolve_nominatim(query: str) -> Location | None:
    url = f"https://nominatim.openstreetmap.org/search?q={quote(query)}&format=json&limit=1"
    request = Request(url, headers={"User-Agent": "pyylmao-reconstruction/0.1"})
    try:
        with urlopen(request, timeout=5) as response:
            data = json.loads(response.read(200_000).decode("utf-8"))
    except (HTTPError, URLError, OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, list) or not data:
        return None
    item = data[0]
    if not isinstance(item, dict):
        return None
    try:
        return Location(
            name=str(item.get("display_name") or query),
            lat=float(item["lat"]),
            lon=float(item["lon"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def location_entries() -> dict[str, Location]:
    raw = {
        "india": Location("India", 22.3511, 78.6677),
        "mexico": Location("Mexico", 23.6585, -102.0077),
        "egypt": Location("Egypt", 26.8206, 30.8025),
        "mongolia": Location("Mongolia", 46.8250, 103.8490),
        "ireland": Location("Ireland", 53.4129, -8.2439),
        "thailand": Location("Thailand", 15.8700, 100.9925),
        "china": Location("China", 35.0000, 103.0000),
        "russia": Location("Russia", 61.5240, 105.3188),
        "sweden": Location("Sweden", 60.1282, 18.6435),
        "kurdistan": Location("Kurdistan", 37.0000, 43.0000),
        "iran": Location("Iran", 32.4279, 53.6880),
        "morocco": Location("Morocco", 31.7917, -7.0926),
        "nepal": Location("Nepal", 28.3949, 84.1240),
        "siberia": Location("Siberia", 60.0000, 105.0000),
        "germany": Location("Germany", 51.1657, 10.4515),
        "alaska": Location("Alaska", 64.2008, -149.4937),
        "korea": Location("Korea", 36.5000, 127.8000),
        "greece": Location("Greece", 39.0742, 21.8243),
        "israel": Location("Israel", 31.0461, 34.8516),
        "uzbekistan": Location("Uzbekistan", 41.3775, 64.5853),
        "romania": Location("Romania", 45.9432, 24.9668),
        "tatarstan": Location("Tatarstan", 55.1802, 50.7264),
        "tajikistan": Location("Tajikistan", 38.8610, 71.2761),
        "iceland": Location("Iceland", 64.9631, -19.0208),
        "finland": Location("Finland", 61.9241, 25.7482),
        "tibet": Location("Tibet", 31.6927, 88.0924),
        "azerbaijan": Location("Azerbaijan", 40.1431, 47.5769),
        "bulgaria": Location("Bulgaria", 42.7339, 25.4858),
        "ukraine": Location("Ukraine", 48.3794, 31.1656),
        "turkey": Location("Turkey", 38.9637, 35.2433),
        "poland": Location("Poland", 51.9194, 19.1451),
        "kazakhstan": Location("Kazakhstan", 48.0196, 66.9237),
        "moldova": Location("Moldova", 47.4116, 28.3699),
        "afghanistan": Location("Afghanistan", 33.9391, 67.7100),
        "iraq": Location("Iraq", 33.2232, 43.6793),
        "syria": Location("Syria", 34.8021, 38.9968),
        "hawaii": Location("Hawaii", 19.8968, -155.5828),
        "java": Location("Java", -7.6145, 110.7122),
        "sri lanka": Location("Sri Lanka", 7.8731, 80.7718),
        "lebanon": Location("Lebanon", 33.8547, 35.8623),
        "malaysia": Location("Malaysia", 4.2105, 101.9758),
        "myanmar": Location("Myanmar", 21.9162, 95.9560),
        "laos": Location("Laos", 19.8563, 102.4955),
        "bangladesh": Location("Bangladesh", 23.6850, 90.3563),
        "punjab": Location("Punjab", 31.1471, 75.3412),
        "turkmenistan": Location("Turkmenistan", 38.9697, 59.5563),
        "dagestan": Location("Dagestan", 43.0575, 47.1332),
        "belarus": Location("Belarus", 53.7098, 27.9534),
        "serbia": Location("Serbia", 44.0165, 21.0059),
        "latvia": Location("Latvia", 56.8796, 24.6032),
        "estonia": Location("Estonia", 58.5953, 25.0136),
        "norway": Location("Norway", 60.4720, 8.4689),
        "denmark": Location("Denmark", 56.2639, 9.5018),
        "lithuania": Location("Lithuania", 55.1694, 23.8813),
        "sapmi": Location("Sapmi", 68.0000, 24.0000),
        "georgia": Location("Georgia", 42.3154, 43.3569),
        "new zealand": Location("New Zealand", -40.9006, 174.8860),
        "papua new guinea": Location("Papua New Guinea", -6.3150, 143.9555),
        "ethiopia": Location("Ethiopia", 9.1450, 40.4897),
        "france": Location("France", 46.2276, 2.2137),
        "chile": Location("Chile", -35.6751, -71.5430),
        "sudan": Location("Sudan", 12.8628, 30.2176),
        "south sudan": Location("South Sudan", 6.8770, 31.3070),
        "drc": Location("DRC", -2.9814, 23.8223),
        "paraguay": Location("Paraguay", -23.4425, -58.4438),
        "falkland islands": Location("Falkland Islands", -51.7963, -59.5236),
        "brazil": Location("Brazil", -14.2350, -51.9253),
        "argentina": Location("Argentina", -38.4161, -63.6167),
        "gambia": Location("Gambia", 13.4432, -15.3101),
        "vietnam": Location("Vietnam", 14.0583, 108.2772),
        "cambodia": Location("Cambodia", 12.5657, 104.9910),
        "philippines": Location("Philippines", 12.8797, 121.7740),
        "micronesia": Location("Micronesia", 7.4256, 150.5508),
        "easter island": Location("Easter Island", -27.1127, -109.3497),
        "bangkok": Location("Bangkok", 13.7563, 100.5018),
        "haiti": Location("Haiti", 18.9712, -72.2852),
        "libya": Location("Libya", 26.3351, 17.2283),
        "nicaragua": Location("Nicaragua", 12.8654, -85.2072),
        "albania": Location("Albania", 41.1533, 20.1683),
        "australia": Location("Australia", -25.2744, 133.7751),
    }
    aliases = {
        "indian": "india",
        "egyptian": "egypt",
        "mongolian": "mongolia",
        "irish": "ireland",
        "thai": "thailand",
        "chinese": "china",
        "russian": "russia",
        "swedish": "sweden",
        "kurd": "kurdistan",
        "iranian": "iran",
        "moroccan": "morocco",
        "nepali": "nepal",
        "siberian": "siberia",
        "east siberian": "siberia",
        "west siberian": "siberia",
        "german": "germany",
        "alaskan": "alaska",
        "korean": "korea",
        "greek": "greece",
        "jewish": "israel",
        "uzbek": "uzbekistan",
        "romanian": "romania",
        "tatar": "tatarstan",
        "tajik": "tajikistan",
        "icelandic": "iceland",
        "finnish": "finland",
        "tibetan": "tibet",
        "azerbaijani": "azerbaijan",
        "bulgarian": "bulgaria",
        "ukrainian": "ukraine",
        "turkish": "turkey",
        "turk": "turkey",
        "polish": "poland",
        "kazakh": "kazakhstan",
        "moldovan": "moldova",
        "afghani": "afghanistan",
        "afghan": "afghanistan",
        "iraqi": "iraq",
        "syrian": "syria",
        "hawaiian": "hawaii",
        "javan": "java",
        "sri lankan": "sri lanka",
        "sri lanken": "sri lanka",
        "lebanese": "lebanon",
        "malay": "malaysia",
        "burmese": "myanmar",
        "lao": "laos",
        "bangla": "bangladesh",
        "bangladeshi": "bangladesh",
        "punjabi": "punjab",
        "belarusian": "belarus",
        "serbian": "serbia",
        "latvian": "latvia",
        "estonian": "estonia",
        "norwegian": "norway",
        "danish": "denmark",
        "lithuanian": "lithuania",
        "saami": "sapmi",
        "sami": "sapmi",
        "georgian": "georgia",
        "png": "papua new guinea",
        "ethiopian": "ethiopia",
        "french": "france",
        "chilean": "chile",
        "sudanese": "sudan",
        "congo": "drc",
        "dr congo": "drc",
        "congolese": "drc",
        "polynesia": "easter island",
        "bali": "java",
        "burma": "myanmar",
        "hatian": "haiti",
        "american": "usa",
        "southafrica": "south africa",
    }
    raw["usa"] = Location("USA", 39.8283, -98.5795)
    raw["south africa"] = Location("South Africa", -30.5595, 22.9375)
    for alias, target in aliases.items():
        if target in raw:
            raw[alias] = raw[target]
    return raw


DEFAULT_LOCATIONS = location_entries()


DEFAULT_PHENOTYPES: tuple[PhenotypeEntry, ...] = (
    PhenotypeEntry("indodravidian", "Indo-Dravidian", 20.6, 78.9, ("india", "indian")),
    PhenotypeEntry("southpalaungid", "South Palaungid", 18.0, 102.6, ("laos", "lao"), ("vietnam", "thai")),
    PhenotypeEntry("polynesid", "Polynesian", -17.7, -149.4, ("french polynesia", "tahiti"), ("new zealand", "samoa", "tonga")),
    PhenotypeEntry("melanesid", "Melanesid", -6.3, 147.0, ("papua new guinea", "png"), ("new guinea",)),
    PhenotypeEntry("sinoeuropid", "Sino-Europid", 31.3, 87.4, ("tibet", "tibetan")),
    PhenotypeEntry("nilotes", "Nilotes", 7.0, 30.0, ("sudan", "south sudan", "sudanese"), ("drc", "ethiopia")),
    PhenotypeEntry("indoafghan", "Indo-Afghan", 34.5, 69.2, ("afghanistan", "afghan"), ("pakistan",)),
    PhenotypeEntry("patagonid", "Patagonid", -45.0, -70.0, ("chile", "chilean", "patagonia")),
    PhenotypeEntry("botocudo", "Botocudo", -15.0, -55.0, ("brazil",), ("paraguay",)),
    PhenotypeEntry("southfuegid", "South Fuegid", -53.8, -68.3, ("tierra del fuego",), ("falkland islands", "argentina", "chile")),
    PhenotypeEntry("adriatic", "Adriatic", 43.5, 16.4, ("croatia",), ("italian", "french", "albania")),
    PhenotypeEntry("western", "Western [Europe]", 47.0, 2.0, ("france", "french"), ("greek", "italy")),
    PhenotypeEntry("nilo_hamitic", "Nilo Hamitic", 9.1, 40.5, ("ethiopia", "ethiopian"), ("kenya",)),
    PhenotypeEntry("homo_sudanensis", "Homo sudanensis", 13.5, 30.0, ("sudan",), ("gambia",)),
    PhenotypeEntry("homo_mongoloideus", "Homo mongoloideus", 60.0, 100.0, ("siberia", "siberian", "east siberian"), ("mongolia",)),
    PhenotypeEntry("arabid", "South Oriental", 24.0, 45.0, ("saudi", "arabia", "yemen"), ("iraq", "syria")),
    PhenotypeEntry("dinarid", "Dinarid", 44.0, 18.0, ("serbia", "bosnia", "croatia"), ("albania", "greece")),
    PhenotypeEntry("fennonordid", "Fenno Nordid", 62.0, 26.0, ("finland", "finnish"), ("sweden", "russia")),
)
