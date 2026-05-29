from __future__ import annotations

import unittest

from pyylmao.weather import WeatherRenderers, render_current_weather, render_forecast


class StaticWeatherProvider:
    def __init__(self, payload: dict):
        self.payload = payload
        self.locations: list[str] = []

    def fetch(self, location: str) -> dict:
        self.locations.append(location)
        return self.payload


def sample_payload() -> dict:
    return {
        "current_condition": [
            {
                "weatherCode": "116",
                "temp_C": "5",
                "winddir16Point": "E",
                "windspeedKmph": "12",
                "humidity": "100",
                "precipMM": "0",
                "uvIndex": "0",
            }
        ],
        "weather": [
            {
                "date": "2026-05-23",
                "maxtempC": "18",
                "hourly": [{"time": "1200", "weatherCode": "116", "chanceofrain": "10", "cloudcover": "60"}],
            },
            {
                "date": "2026-05-24",
                "maxtempC": "18",
                "hourly": [{"time": "1200", "weatherCode": "176", "chanceofrain": "70", "cloudcover": "80"}],
            },
            {
                "date": "2026-05-25",
                "maxtempC": "13",
                "hourly": [{"time": "1200", "weatherCode": "308", "chanceofrain": "95", "cloudcover": "100"}],
            },
            {
                "date": "2026-05-26",
                "maxtempC": "17",
                "hourly": [{"time": "1200", "weatherCode": "116", "chanceofrain": "0", "cloudcover": "40"}],
            },
            {
                "date": "2026-05-27",
                "maxtempC": "18",
                "hourly": [{"time": "1200", "weatherCode": "116", "chanceofrain": "0", "cloudcover": "40"}],
            },
            {
                "date": "2026-05-28",
                "maxtempC": "17",
                "hourly": [{"time": "1200", "weatherCode": "116", "chanceofrain": "0", "cloudcover": "40"}],
            },
            {
                "date": "2026-05-29",
                "maxtempC": "17",
                "hourly": [{"time": "1200", "weatherCode": "116", "chanceofrain": "0", "cloudcover": "40"}],
            },
        ],
    }


class WeatherTests(unittest.TestCase):
    def test_current_weather_matches_logged_shape(self) -> None:
        self.assertEqual(
            render_current_weather(sample_payload()),
            "⛅ 5°C | E 12km/h | 100% RH | 0.0mm | UV: 0 burn after unlimited",
        )

    def test_weather_usage_and_provider_location(self) -> None:
        provider = StaticWeatherProvider(sample_payload())
        renderers = WeatherRenderers(provider)
        self.assertEqual(renderers.weather("!weather"), ["Usage: !weather <location>"])
        self.assertEqual(
            renderers.weather("!weather vancouver, bc"),
            ["⛅ 5°C | E 12km/h | 100% RH | 0.0mm | UV: 0 burn after unlimited"],
        )
        self.assertEqual(provider.locations, ["vancouver, bc"])

    def test_forecast_table_matches_logged_shape(self) -> None:
        lines = render_forecast(sample_payload())
        self.assertEqual(lines[0], "┌─────┬─────┬─────┬─────┬─────┬─────┬─────┐")
        self.assertEqual(lines[1], "│ Sat │ Sun │ Mon │ Tue │ Wed │ Thu │ Fri │")
        self.assertEqual(lines[2], "├─────┼─────┼─────┼─────┼─────┼─────┼─────┤")
        self.assertEqual(lines[4], "│ 18C │ 18C │ 13C │ 17C │ 18C │ 17C │ 17C │")
        self.assertEqual(lines[5], "└─────┴─────┴─────┴─────┴─────┴─────┴─────┘")


if __name__ == "__main__":
    unittest.main()
