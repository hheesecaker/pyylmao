from __future__ import annotations

import unittest

from pyylmao.random_command import render_random_command


class FixedRandom:
    def __init__(self):
        self.calls: list[tuple[int, int]] = []

    def randint(self, a: int, b: int) -> int:
        self.calls.append((a, b))
        return b


class RandomCommandTests(unittest.TestCase):
    def test_render_random_command_matches_generated_output_shape(self) -> None:
        rng = FixedRandom()

        self.assertEqual(render_random_command(".random", rng), ["Random number: 100"])
        self.assertEqual(render_random_command(".random 50", rng), ["Random number between 1 and 50: 50"])
        self.assertEqual(render_random_command(".random 1 3", rng), ["Random number between 1 and 3: 3"])
        self.assertEqual(rng.calls, [(1, 100), (1, 50), (1, 3)])

    def test_render_random_command_preserves_final_errors(self) -> None:
        rng = FixedRandom()

        self.assertEqual(
            render_random_command(".random 3 1", rng),
            ["Error: min cannot be greater than max"],
        )
        self.assertEqual(
            render_random_command(".random 10-20", rng),
            ["Error: Please provide valid numbers"],
        )
        self.assertEqual(
            render_random_command(".random 1 2 3", rng),
            ["Usage: .random [min max] or .random [max]"],
        )


if __name__ == "__main__":
    unittest.main()
