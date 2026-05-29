from __future__ import annotations

import os
import tempfile
import unittest
import wave
from pathlib import Path

from pyylmao.vocoder import (
    VocoderSynthesizer,
    is_vocoder_command,
    parse_vocoder_command,
    render_vocoder_command,
)


class VocoderTests(unittest.TestCase):
    def test_detects_logged_final_and_legacy_triggers(self) -> None:
        self.assertTrue(is_vocoder_command("!vocoder won too three"))
        self.assertTrue(is_vocoder_command("vocoder huh.wav one two three"))
        self.assertFalse(is_vocoder_command("!vocoder"))

    def test_parse_final_trigger_uses_logged_random_subdir_shape(self) -> None:
        request = parse_vocoder_command("!vocoder hello world", filename_seed=b"fixed")
        self.assertEqual(request.text, "hello world")
        self.assertRegex(request.relative_name, r"^2/[0-9a-f]{12}\.wav$")

    def test_parse_legacy_trigger_preserves_requested_filename(self) -> None:
        request = parse_vocoder_command("vocoder huh.wav does this work")
        self.assertEqual(request.text, "does this work")
        self.assertEqual(request.relative_name, "huh.wav")

    def test_render_writes_public_wav_url(self) -> None:
        old_base_url = os.environ.get("PYYLMAO_WWW_BASE_URL")
        os.environ["PYYLMAO_WWW_BASE_URL"] = "https://cte.example"
        self.addCleanup(self.restore_env, "PYYLMAO_WWW_BASE_URL", old_base_url)
        with tempfile.TemporaryDirectory() as tmp:
            lines = render_vocoder_command(
                "!vocoder I wish to purchase an automobile.",
                output_dir=tmp,
                filename_seed=b"fixed",
            )
            self.assertEqual(lines, ["https://cte.example/2/af0e6ad3bd60.wav"])
            path = Path(tmp) / "2" / "af0e6ad3bd60.wav"
            self.assertTrue(path.exists())
            with wave.open(str(path), "rb") as handle:
                self.assertEqual(handle.getnchannels(), 1)
                self.assertEqual(handle.getsampwidth(), 2)
                self.assertEqual(handle.getframerate(), 22050)
                self.assertGreater(handle.getnframes(), 1000)

    def test_synthesizer_is_dependency_free_and_nonempty(self) -> None:
        samples = VocoderSynthesizer().synthesize("hello test")
        self.assertGreater(len(samples), 1000)
        self.assertLessEqual(max(abs(sample) for sample in samples), 1.0)

    @staticmethod
    def restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
