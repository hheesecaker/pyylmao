from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol


class WeatherCommandError(Exception):
    pass


class WeatherProvider(Protocol):
    def fetch(self, location: str) -> dict:
        ...


class WttrWeatherProvider:
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def fetch(self, location: str) -> dict:
        encoded = urllib.parse.quote(location.strip(), safe=",")
        url = f"https://wttr.in/{encoded}?format=j1"
        request = urllib.request.Request(url, headers={"User-Agent": "pyylmao/0.1"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))


class OpenMeteoForecastProvider:
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def fetch(self, location: str) -> dict:
        place = self.geocode(location)
        query = urllib.parse.urlencode(
            {
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "daily": "weather_code,temperature_2m_max",
                "forecast_days": "7",
                "timezone": "auto",
            }
        )
        url = f"https://api.open-meteo.com/v1/forecast?{query}"
        request = urllib.request.Request(url, headers={"User-Agent": "pyylmao/0.1"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        daily = payload.get("daily") or {}
        dates = daily.get("time") or []
        codes = daily.get("weather_code") or []
        temps = daily.get("temperature_2m_max") or []
        weather = []
        for date, code, temp in zip(dates, codes, temps):
            weather.append(
                {
                    "date": date,
                    "maxtempC": str(int_value(temp, 0)),
                    "icon": open_meteo_icon(int_value(code, 3)),
                }
            )
        return {"weather": weather}

    def geocode(self, location: str) -> dict:
        for term in geocode_terms(location):
            query = urllib.parse.urlencode(
                {"name": term, "count": "1", "language": "en", "format": "json"}
            )
            url = f"https://geocoding-api.open-meteo.com/v1/search?{query}"
            request = urllib.request.Request(url, headers={"User-Agent": "pyylmao/0.1"})
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            results = payload.get("results") or []
            if results:
                return results[0]
        raise WeatherCommandError(f"Location not found: {location}")


class WeatherRenderers:
    def __init__(
        self,
        provider: WeatherProvider,
        forecast_provider: WeatherProvider | None = None,
    ):
        self.provider = provider
        self.forecast_provider = forecast_provider or provider

    def weather(self, text: str) -> list[str]:
        location = text.strip()[len("!weather") :].strip()
        if not location:
            return ["Usage: !weather <location>"]
        try:
            payload = self.provider.fetch(location)
            return [render_current_weather(payload)]
        except WeatherCommandError:
            raise
        except Exception as exc:
            raise WeatherCommandError(f"Error retrieving weather data: {exc}") from exc

    def forecast(self, text: str) -> list[str]:
        location = text.strip()[len("!forecast") :].strip()
        if not location:
            return ["Usage: !forecast <location>"]
        try:
            payload = self.forecast_provider.fetch(location)
            return render_forecast(payload)
        except WeatherCommandError:
            raise
        except Exception as exc:
            raise WeatherCommandError(f"Error retrieving forecast data: {exc}") from exc


def default_weather_renderers() -> WeatherRenderers:
    return WeatherRenderers(WttrWeatherProvider(), OpenMeteoForecastProvider())


def render_current_weather(payload: dict) -> str:
    conditions = payload.get("current_condition") or []
    if not conditions:
        raise WeatherCommandError("Error retrieving weather data: no current conditions")
    current = conditions[0]
    code = int_value(current.get("weatherCode"), 0)
    temp = int_value(current.get("temp_C"), 0)
    wind = int_value(current.get("windspeedKmph"), 0)
    humidity = int_value(current.get("humidity"), 0)
    precip = one_decimal(current.get("precipMM"))
    uv = int_value(current.get("uvIndex"), 0)
    wind_dir = str(current.get("winddir16Point") or "?")
    return (
        f"{weather_icon(code)} {temp}°C | {wind_dir} {wind}km/h | {humidity}% RH | "
        f"{precip}mm | UV: {uv} burn after {uv_burn_after(uv)}"
    )


def render_forecast(payload: dict) -> list[str]:
    days = (payload.get("weather") or [])[:7]
    if not days:
        raise WeatherCommandError("Error retrieving forecast data: no forecast")
    labels = [weekday(day.get("date")) for day in days]
    icons = [forecast_day_icon(day) for day in days]
    temps = [f"{int_value(day.get('maxtempC'), 0)}C" for day in days]
    return [
        "┌" + "┬".join("─────" for _ in days) + "┐",
        forecast_row(labels),
        "├" + "┼".join("─────" for _ in days) + "┤",
        forecast_row(icons),
        forecast_row(temps),
        "└" + "┴".join("─────" for _ in days) + "┘",
    ]


def forecast_row(items: list[str]) -> str:
    return "│" + "│".join(f" {item:^3} " for item in items) + "│"


def weekday(raw: object) -> str:
    if raw is None:
        return "???"
    try:
        return datetime.strptime(str(raw), "%Y-%m-%d").strftime("%a")
    except ValueError:
        return "???"


def forecast_day_icon(day: dict) -> str:
    explicit = day.get("icon")
    if explicit:
        return str(explicit)
    hourly = day.get("hourly") or []
    if not hourly:
        return weather_icon(int_value(day.get("weatherCode"), 0))
    best = max(hourly, key=hour_score)
    return weather_icon(int_value(best.get("weatherCode"), 0))


def hour_score(hour: dict) -> tuple[int, int]:
    rain = int_value(hour.get("chanceofrain"), 0)
    snow = int_value(hour.get("chanceofsnow"), 0)
    thunder = int_value(hour.get("chanceofthunder"), 0)
    cloud = int_value(hour.get("cloudcover"), 0)
    time = int_value(hour.get("time"), 0)
    daytime_bias = -abs(time - 1200)
    return (max(rain, snow, thunder), cloud, daytime_bias)


def weather_icon(code: int) -> str:
    if code == 113:
        return "☀️"
    if code in {116}:
        return "⛅"
    if code in {119, 122}:
        return "☁️"
    if code in {143, 248, 260}:
        return "🌫️"
    if code in {176, 263, 293}:
        return "🌦️"
    if code in {179, 182, 185, 227, 230, 317, 320, 323, 326, 329, 332, 335, 338, 350, 362, 365, 368, 371, 374, 377}:
        return "🌨️"
    if code in {200, 386, 389, 392, 395}:
        return "⛈️"
    if code in {266, 281, 284, 296, 299, 302, 305, 308, 311, 314, 353, 356, 359}:
        return "🌧️"
    return "☁️"


def open_meteo_icon(code: int) -> str:
    if code == 0:
        return "☀️"
    if code in {1, 2}:
        return "⛅"
    if code == 3:
        return "☁️"
    if code in {45, 48}:
        return "🌫️"
    if code in {51, 53, 55, 56, 57, 80}:
        return "🌦️"
    if code in {61, 63, 65, 66, 67, 81, 82}:
        return "🌧️"
    if code in {71, 73, 75, 77, 85, 86}:
        return "🌨️"
    if code in {95, 96, 99}:
        return "⛈️"
    return "☁️"


def geocode_terms(location: str) -> list[str]:
    raw = location.strip()
    terms = [raw]
    if "," in raw:
        first = raw.split(",", 1)[0].strip()
        if first and first not in terms:
            terms.append(first)
    return terms


def uv_burn_after(uv: int) -> str:
    if uv <= 2:
        return "unlimited"
    if uv == 3:
        return "55 min"
    if uv == 4:
        return "45 min"
    if uv == 5:
        return "35 min"
    if uv <= 7:
        return "25 min"
    if uv <= 10:
        return "15 min"
    return "10 min"


def int_value(raw: object, default: int) -> int:
    try:
        return int(Decimal(str(raw)).to_integral_value())
    except (InvalidOperation, ValueError):
        return default


def one_decimal(raw: object) -> str:
    try:
        return f"{Decimal(str(raw)):.1f}"
    except (InvalidOperation, ValueError):
        return "0.0"
