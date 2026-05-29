from __future__ import annotations

import unittest

from pyylmao.models import (
    format_context,
    is_models_command,
    newest_models,
    render_models_command,
)


class FakeProvider:
    def __init__(self, models: list[dict]):
        self._models = models

    def models(self) -> list[dict]:
        return self._models


class ModelsTests(unittest.TestCase):
    def test_detects_exact_logged_command(self) -> None:
        self.assertTrue(is_models_command("!models"))
        self.assertTrue(is_models_command("  !MODELS  "))
        self.assertFalse(is_models_command("!models gpt"))

    def test_renders_recent_openrouter_models(self) -> None:
        provider = FakeProvider(
            [
                {
                    "id": "older/model",
                    "created": 100,
                    "context_length": 8192,
                    "pricing": {"prompt": "0.0000001", "completion": "0.0000002"},
                },
                {
                    "id": "newer/model",
                    "created": 200,
                    "context_length": 1000000,
                    "pricing": {"prompt": "0.00000125", "completion": "0.00000375"},
                },
            ]
        )
        lines = render_models_command("!models", provider=provider)
        self.assertEqual(lines[0], "OpenRouter models")
        self.assertIn("MODEL", lines[1])
        self.assertIn("newer/model", lines[2])
        self.assertIn("1000k", lines[2])
        self.assertIn("$1.25", lines[2])
        self.assertIn("$3.75", lines[2])
        self.assertIn("older/model", lines[3])

    def test_limits_rows(self) -> None:
        provider = FakeProvider(
            [
                {"id": "third", "created": 3, "context_length": 1, "pricing": {}},
                {"id": "second", "created": 2, "context_length": 1, "pricing": {}},
                {"id": "first", "created": 1, "context_length": 1, "pricing": {}},
            ]
        )
        lines = render_models_command("!models", provider=provider, limit=2)
        self.assertIn("third", "\n".join(lines))
        self.assertIn("second", "\n".join(lines))
        self.assertNotIn("first", "\n".join(lines))

    def test_newest_models_sort_missing_created_as_oldest(self) -> None:
        sorted_models = newest_models([{"id": "old"}, {"id": "new", "created": 10}])
        self.assertEqual([model["id"] for model in sorted_models], ["new", "old"])

    def test_format_context(self) -> None:
        self.assertEqual(format_context(8192), "8.2k")
        self.assertEqual(format_context(128000), "128k")
        self.assertEqual(format_context(None), "?")


if __name__ == "__main__":
    unittest.main()
