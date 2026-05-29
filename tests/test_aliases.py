from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyylmao.aliases import (
    AliasStore,
    alias_usage,
    normalize_model_id,
    valid_alias_name,
)
from pyylmao.state import JsonState


class AliasStoreTests(unittest.TestCase):
    def make_store(self, defaults: dict[str, str] | None = None) -> tuple[AliasStore, Path]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "state.json"
        return AliasStore(JsonState(path), defaults=defaults), path

    def test_usage_and_unknown_command_match_logged_shape(self) -> None:
        store, _ = self.make_store(defaults={"grok": "openrouter/x-ai/grok-4.1-fast"})
        self.assertEqual(store.handle("!alias"), alias_usage())
        self.assertEqual(
            store.handle("!alias oeu"),
            [
                "Unknown command: 'oeu'. Use list, get, set, delete, set-default, or get-default.",
                *alias_usage(),
            ],
        )

    def test_get_set_list_delete_and_persistence(self) -> None:
        store, path = self.make_store(defaults={"grok": "openrouter/x-ai/grok-4.1-fast"})

        self.assertEqual(store.handle("!alias get grok"), ["'grok' -> 'openrouter/x-ai/grok-4.1-fast'"])
        self.assertEqual(
            store.handle("!alias set glm openrouter/z-ai/glm-4.7"),
            ["Alias 'glm' set to 'openrouter/z-ai/glm-4.7'."],
        )
        self.assertIn("'glm' -> 'openrouter/z-ai/glm-4.7'", store.handle("!alias list"))

        reloaded = AliasStore(JsonState(path), defaults={"grok": "openrouter/x-ai/grok-4.1-fast"})
        self.assertEqual(reloaded.handle("!alias get glm"), ["'glm' -> 'openrouter/z-ai/glm-4.7'"])
        self.assertEqual(reloaded.handle("!alias delete glm"), ["Alias 'glm' removed."])
        self.assertEqual(reloaded.handle("!alias get glm"), ["Alias 'glm' not found."])

    def test_delete_tombstones_default_alias_until_re_set(self) -> None:
        store, path = self.make_store(defaults={"sonoma": "openrouter/sonoma-sky-alpha"})
        self.assertEqual(store.handle("!alias delete sonoma"), ["Alias 'sonoma' removed."])
        self.assertEqual(store.handle("!alias get sonoma"), ["Alias 'sonoma' not found."])

        reloaded = AliasStore(JsonState(path), defaults={"sonoma": "openrouter/sonoma-sky-alpha"})
        self.assertEqual(reloaded.handle("!alias get sonoma"), ["Alias 'sonoma' not found."])
        self.assertEqual(
            reloaded.handle("!alias set sonoma openrouter/sonoma-sky-alpha"),
            ["Alias 'sonoma' set to 'openrouter/sonoma-sky-alpha'."],
        )
        self.assertEqual(
            reloaded.handle("!alias get sonoma"),
            ["'sonoma' -> 'openrouter/sonoma-sky-alpha'"],
        )

    def test_slash_alias_names_seen_in_logs_are_valid(self) -> None:
        store, _ = self.make_store(defaults={})
        self.assertTrue(valid_alias_name("moonshotai/kimi-k2.5"))
        self.assertEqual(
            store.handle("!alias set moonshotai/kimi-k2.5 moonshot/kimi-k2.5"),
            ["Alias 'moonshotai/kimi-k2.5' set to 'moonshot/kimi-k2.5'."],
        )
        self.assertEqual(
            store.handle("!alias get moonshotai/kimi-k2.5"),
            ["'moonshotai/kimi-k2.5' -> 'moonshot/kimi-k2.5'"],
        )

    def test_default_model_can_be_set_to_alias_or_model_id(self) -> None:
        store, _ = self.make_store(defaults={"gpt": "openrouter/openai/gpt-oss-120b", "flash": "gemini/gemini-2.0-flash"})

        self.assertEqual(store.default_model(), "openrouter/openai/gpt-oss-120b")
        self.assertEqual(store.handle("!alias set-default flash"), ["Default model set to 'flash'."])
        self.assertEqual(store.default_model(), "gemini/gemini-2.0-flash")
        self.assertEqual(store.handle("!alias get-default"), ["Default model: 'gemini/gemini-2.0-flash'"])
        self.assertEqual(
            store.handle("!alias set-default openrouter/x-ai/grok-4.3"),
            ["Default model set to 'openrouter/x-ai/grok-4.3'."],
        )
        self.assertEqual(store.default_model(), "openrouter/x-ai/grok-4.3")

    def test_normalize_model_id_strips_openrouter_router_prefix_only(self) -> None:
        self.assertEqual(normalize_model_id("openrouter/x-ai/grok-4.3"), "x-ai/grok-4.3")
        self.assertEqual(normalize_model_id("gpt-5-mini"), "gpt-5-mini")
        self.assertEqual(normalize_model_id(" moonshot/kimi-latest "), "moonshot/kimi-latest")


if __name__ == "__main__":
    unittest.main()
