from __future__ import annotations

import unittest

from pyylmao.fortune import (
    BROKEN_LINE,
    SOLID_LINE,
    HEXAGRAM_BY_LINES,
    is_fortune_command,
    parse_fortune_prompt,
    render_fortune_command,
)


class FortuneTests(unittest.TestCase):
    def test_detects_fortune_command(self) -> None:
        self.assertTrue(is_fortune_command("!fortune"))
        self.assertTrue(is_fortune_command("!fortune should I proceed"))
        self.assertFalse(is_fortune_command("!fortunex should I proceed"))

    def test_parses_optional_prompt(self) -> None:
        self.assertEqual(parse_fortune_prompt("!fortune"), "")
        self.assertEqual(parse_fortune_prompt("!fortune  test, disregard "), "test, disregard")

    def test_hexagram_mapping_matches_logged_examples(self) -> None:
        self.assertEqual(HEXAGRAM_BY_LINES[(True, True, True, True, True, True)], 1)
        self.assertEqual(HEXAGRAM_BY_LINES[(True, True, False, False, True, False)], 60)
        self.assertEqual(HEXAGRAM_BY_LINES[(True, True, False, False, False, False)], 19)
        self.assertEqual(HEXAGRAM_BY_LINES[(False, False, False, False, True, False)], 8)
        self.assertEqual(HEXAGRAM_BY_LINES[(False, True, False, False, True, False)], 29)

    def test_renders_unchanging_hexagram_shape(self) -> None:
        lines = render_fortune_command("!fortune is this going to work the first time", [7, 7, 7, 7, 7, 7])
        self.assertIn("1 ䷀", lines[0])
        self.assertNotIn("changing to", lines[0])
        self.assertEqual(lines[3].split("  ", 1)[0], SOLID_LINE)
        self.assertIn("𝙷𝙴𝚇𝙰𝙶𝚁𝙰𝙼 𝟷", lines[3])
        self.assertIn("𝚃𝙷𝙴 𝙲𝚁𝙴𝙰𝚃𝙸𝚅𝙴", "\n".join(lines))
        self.assertEqual(lines[-1], "stalks thrown: 7 7 7 7 7 7")

    def test_renders_changing_hexagram_shape(self) -> None:
        lines = render_fortune_command("!fortune how do I piss", [7, 7, 8, 8, 9, 8])
        self.assertIn("60 ䷻ changing to 19 ䷒", lines[0])
        self.assertEqual(lines[3][:10], BROKEN_LINE)
        self.assertTrue(lines[3].endswith(BROKEN_LINE))
        self.assertIn("𝙻𝙸𝙼𝙸𝚃𝙰𝚃𝙸𝙾𝙽", "\n".join(lines))
        self.assertIn("𝙰𝙿𝙿𝚁𝙾𝙰𝙲𝙷", "\n".join(lines))
        self.assertEqual(lines[-1], "stalks thrown: 7 7 8 8 9 8")

    def test_rejects_invalid_throw_fixture(self) -> None:
        with self.assertRaises(ValueError):
            render_fortune_command("!fortune", [7, 7, 7])


if __name__ == "__main__":
    unittest.main()
