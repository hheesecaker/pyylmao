from __future__ import annotations

import random
import tempfile
import unittest
from pathlib import Path

from pyylmao.phenoguessr import (
    Location,
    PhenoguessrStore,
    PhenotypeEntry,
    StaticLocationResolver,
    format_number,
    haversine_km,
    is_phenoguessr_command,
    score_for_distance,
)
from pyylmao.state import JsonState


class PhenoguessrTests(unittest.TestCase):
    def make_store(
        self,
        image_renderer=None,
    ) -> tuple[PhenoguessrStore, JsonState, tempfile.TemporaryDirectory[str]]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = JsonState(Path(tmp.name) / "state.json")
        asset_dir = Path(tmp.name) / "assets"
        (asset_dir / "sample").mkdir(parents=True)
        (asset_dir / "sample" / "male.jpg").write_bytes(b"not-a-real-image")
        store = PhenoguessrStore(
            state,
            entries=[
                PhenotypeEntry(
                    "sample",
                    "Sample Label",
                    0.0,
                    0.0,
                    accepted=("target",),
                    technical=("near",),
                )
            ],
            resolver=StaticLocationResolver(
                {
                    "target": Location("Target", 0.0, 1.0),
                    "near": Location("Near", 0.0, 10.0),
                    "far": Location("Far", 0.0, 40.0),
                }
            ),
            image_renderer=image_renderer or (lambda command: []),
            asset_dir=asset_dir,
            rng=random.Random(1),
            now=lambda: 1779147183.162254,
        )
        return store, state, tmp

    def test_detects_logged_trigger(self) -> None:
        self.assertTrue(is_phenoguessr_command("!pheno"))
        self.assertTrue(is_phenoguessr_command("!pheno india"))
        self.assertTrue(is_phenoguessr_command("!pheno  cambodia"))
        self.assertFalse(is_phenoguessr_command("!phenotype"))

    def test_start_uses_logged_kv_state_and_img2irc_args(self) -> None:
        commands: list[str] = []

        def image_renderer(command: str) -> list[str]:
            commands.append(command)
            return ["IMG"]

        store, state, _ = self.make_store(image_renderer=image_renderer)
        root = state.data["kvstore"]["commands"]["phenoguessr"]
        root["output_mode"] = "img2irc"
        root["img2irc_args"] = {
            "width": 72,
            "render": "ansi24",
            "blocks": "default",
            "contrast": 20,
        }

        self.assertEqual(
            store.handle("alice", "!pheno"),
            ["IMG", "New phenotype guesser started! Guess the location with !pheno <location>"],
        )
        self.assertEqual(root["current_pheno"], "sample")
        self.assertEqual(root["current_pheno_label"], "Sample Label")
        self.assertEqual(root["current_gender"], "male")
        self.assertEqual(root["last_guess_time"], 1779147183.162254)
        self.assertEqual(root["recent_phenos"], ["sample"])
        self.assertIn("!img2irc", commands[0])
        self.assertIn("sample/male.jpg", commands[0])
        self.assertIn("width 72", commands[0])
        self.assertIn("render ansi24", commands[0])
        self.assertIn("blocks default", commands[0])
        self.assertIn("contrast 20", commands[0])
        self.assertNotIn("brightness", commands[0])
        self.assertNotIn("nograyscale", commands[0])

    def test_guess_outputs_logged_wrong_correct_and_missing_game_shapes(self) -> None:
        store, state, _ = self.make_store()

        self.assertEqual(
            store.handle("alice", "!pheno far"),
            ["No active game. Start one with !pheno"],
        )

        store.handle("alice", "!pheno")
        wrong = store.handle("alice", "!pheno far")
        self.assertEqual(
            wrong,
            ["alice guessed far. Incorrect! 4447.8 km (2763.73 mi) away."],
        )
        stats = state.data["kvstore"]["commands"]["phenoguessr"]["stats"]["alice"]
        self.assertEqual(stats["incorrect_guesses"], 1)
        self.assertEqual(stats["correct_guesses"], 0)

        correct = store.handle("alice", "!pheno target")
        self.assertEqual(
            correct,
            ["alice guessed target! BULLSEYE! Score: 5000 (111.19 km away). It was Sample Label! They win!"],
        )
        root = state.data["kvstore"]["commands"]["phenoguessr"]
        self.assertNotIn("current_pheno", root)
        self.assertEqual(root["stats"]["alice"]["correct_guesses"], 1)
        self.assertEqual(root["stats"]["alice"]["total_score"], 5000)

    def test_unresolved_and_technical_correct_shapes(self) -> None:
        store, _, _ = self.make_store()
        store.handle("alice", "!pheno")

        self.assertEqual(
            store.handle("alice", "!pheno not a place"),
            ["Could not resolve the location for: 'not a place'"],
        )
        score = score_for_distance(haversine_km(0.0, 0.0, 0.0, 10.0))
        self.assertEqual(
            store.handle("bob", "!pheno near"),
            [f"bob guessed near! Technically correct! Score: {score} (1111.95 km away). It was Sample Label! They win!"],
        )

    def test_format_number_matches_logged_trimmed_decimals(self) -> None:
        self.assertEqual(format_number(3842.0), "3842")
        self.assertEqual(format_number(407.56), "407.56")


if __name__ == "__main__":
    unittest.main()
