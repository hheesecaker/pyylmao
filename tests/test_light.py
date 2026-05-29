from __future__ import annotations

import unittest

from pyylmao.light import is_light_command, parse_light_command, render_light_command


class LightTests(unittest.TestCase):
    def test_command_detection_matches_logged_pattern(self) -> None:
        self.assertTrue(is_light_command("!light red"))
        self.assertTrue(is_light_command("!light orange 500"))
        self.assertTrue(is_light_command("!light 400"))
        self.assertFalse(is_light_command("!light #2E6F40"))
        self.assertFalse(is_light_command("!bulb red"))

    def test_parse_color_and_brightness(self) -> None:
        self.assertEqual(parse_light_command("!light red 500"), ("red", 500))
        self.assertEqual(parse_light_command("!light orange"), ("orange", None))
        self.assertEqual(parse_light_command("!light 300"), (None, 300))
        self.assertEqual(parse_light_command("!light"), (None, None))

    def test_color_change_reply_matches_logs(self) -> None:
        self.assertEqual(render_light_command("!light red"), ["colour changed to    "])
        self.assertEqual(render_light_command("!light darkgreen"), ["colour changed to    "])
        self.assertEqual(render_light_command("!light orange 400"), ["colour changed to    "])

    def test_brightness_only_is_quiet(self) -> None:
        self.assertEqual(render_light_command("!light 400"), [])


if __name__ == "__main__":
    unittest.main()
