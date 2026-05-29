from __future__ import annotations

import hashlib
import math
import os
import random
import re
import secrets
import string
import struct
import wave
from dataclasses import dataclass
from pathlib import Path

from .gay import DEFAULT_WWW_DIR, _base_url


pattern = r"^!vocoder (.+)$"
legacy_pattern = r"^vocoder\s+(\S+)\s+(.+)$"

DEFAULT_SAMPLE_RATE = 22050
MAX_TEXT_CHARS = 360

VOWELS = {
    "a": ((730, 1090), 0.105),
    "e": ((530, 1840), 0.095),
    "i": ((270, 2290), 0.095),
    "o": ((570, 840), 0.105),
    "u": ((300, 870), 0.100),
    "y": ((350, 1900), 0.080),
}

VOICED_CONSONANTS = set("lmnrwvzj")
FRICATIVES = set("sfhx")
STOPS = set("ptkbdgqc")


class VocoderCommandError(ValueError):
    pass


@dataclass(frozen=True)
class VocoderRequest:
    text: str
    relative_name: str


def is_vocoder_command(text: str) -> bool:
    stripped = text.strip()
    if re.match(r"^!vocoder\s+.+$", stripped, flags=re.IGNORECASE):
        return True
    return bool(re.match(r"^vocoder\s+\S+\s+.+$", stripped, flags=re.IGNORECASE))


def render_vocoder_command(
    text: str,
    *,
    output_dir: str | Path | None = None,
    base_url: str | None = None,
    filename_seed: bytes | None = None,
) -> list[str]:
    request = parse_vocoder_command(text, filename_seed=filename_seed)
    directory = Path(output_dir or os.getenv("PYYLMAO_WWW_DIR", DEFAULT_WWW_DIR))
    path = safe_output_path(directory, request.relative_name)
    synthesizer = VocoderSynthesizer(sample_rate=DEFAULT_SAMPLE_RATE)
    samples = synthesizer.synthesize(request.text[:MAX_TEXT_CHARS])
    write_wav(path, samples, DEFAULT_SAMPLE_RATE)
    return [f"{_base_url(base_url).rstrip('/')}/{request.relative_name}"]


def parse_vocoder_command(text: str, *, filename_seed: bytes | None = None) -> VocoderRequest:
    stripped = text.strip()
    legacy = re.match(r"^vocoder\s+(\S+)\s+(.+)$", stripped, flags=re.IGNORECASE)
    if legacy:
        filename, payload = legacy.groups()
        return VocoderRequest(clean_payload(payload), sanitize_wav_filename(filename))
    match = re.match(r"^!vocoder\s+(.+)$", stripped, flags=re.IGNORECASE)
    if not match:
        raise VocoderCommandError("Usage: !vocoder <text>")
    payload = clean_payload(match.group(1))
    if not payload:
        raise VocoderCommandError("Usage: !vocoder <text>")
    return VocoderRequest(payload, f"2/{generated_wav_name(payload, filename_seed)}")


def clean_payload(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def generated_wav_name(payload: str, seed: bytes | None = None) -> str:
    if seed is not None:
        digest = hashlib.sha256(seed + payload.encode("utf-8", "ignore")).hexdigest()[:12]
    else:
        digest = secrets.token_hex(6)
    return f"{digest}.wav"


def sanitize_wav_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    allowed = set(string.ascii_letters + string.digits + "._-")
    name = "".join(char if char in allowed else "_" for char in name)
    name = name.strip("._")
    if not name:
        raise VocoderCommandError("Invalid WAV filename")
    if not name.lower().endswith(".wav"):
        name = f"{name}.wav"
    return name


def safe_output_path(root: Path, relative_name: str) -> Path:
    target = (root / relative_name).resolve()
    root = root.resolve()
    if root != target and root not in target.parents:
        raise VocoderCommandError("Invalid WAV filename")
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


class VocoderSynthesizer:
    def __init__(self, sample_rate: int = DEFAULT_SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.rng = random.Random(0x51EE)

    def synthesize(self, text: str) -> list[float]:
        text = text.lower()
        samples: list[float] = []
        pitch = 118.0
        for index, char in enumerate(text):
            if char.isspace():
                samples.extend(self.silence(0.045))
                continue
            if char in ",;:":
                samples.extend(self.silence(0.070))
                continue
            if char in ".!?":
                samples.extend(self.silence(0.120))
                continue
            local_pitch = pitch + 14.0 * math.sin(index * 0.73)
            if char in VOWELS:
                formants, duration = VOWELS[char]
                segment = self.vowel(char, local_pitch, formants, duration)
            elif char in VOICED_CONSONANTS:
                segment = self.voiced_consonant(char, local_pitch)
            elif char in FRICATIVES:
                segment = self.noise(0.055, highpass=True)
            elif char in STOPS:
                segment = self.stop(char, local_pitch)
            elif char.isdigit():
                segment = self.synthesize(DIGIT_WORDS.get(char, ""))
            else:
                segment = self.silence(0.020)
            samples = append_crossfade(samples, segment, int(self.sample_rate * 0.006))
        if not samples:
            samples = self.silence(0.20)
        return normalize(samples)

    def vowel(
        self,
        char: str,
        pitch: float,
        formants: tuple[int, int],
        duration: float,
    ) -> list[float]:
        del char
        count = max(1, int(self.sample_rate * duration))
        out: list[float] = []
        f1, f2 = formants
        for index in range(count):
            t = index / self.sample_rate
            buzz = sum(math.sin(2.0 * math.pi * pitch * harmonic * t) / harmonic for harmonic in range(1, 7))
            vowel = (
                0.44 * math.sin(2.0 * math.pi * f1 * t)
                + 0.30 * math.sin(2.0 * math.pi * f2 * t)
                + 0.12 * math.sin(2.0 * math.pi * (f2 + f1) * 0.5 * t)
            )
            out.append((0.58 * buzz + 0.42 * vowel) * envelope(index, count))
        return out

    def voiced_consonant(self, char: str, pitch: float) -> list[float]:
        duration = 0.055 if char not in {"m", "n"} else 0.075
        count = max(1, int(self.sample_rate * duration))
        nasal = char in {"m", "n"}
        frequency = 220.0 if nasal else 320.0
        out = []
        for index in range(count):
            t = index / self.sample_rate
            source = 0.44 * math.sin(2.0 * math.pi * pitch * t)
            resonance = 0.35 * math.sin(2.0 * math.pi * frequency * t)
            breath = 0.06 * (self.rng.random() * 2.0 - 1.0)
            out.append((source + resonance + breath) * envelope(index, count))
        return out

    def noise(self, duration: float, *, highpass: bool = False) -> list[float]:
        count = max(1, int(self.sample_rate * duration))
        out = []
        previous = 0.0
        for index in range(count):
            current = self.rng.random() * 2.0 - 1.0
            value = current - 0.65 * previous if highpass else current
            previous = current
            out.append(0.36 * value * envelope(index, count))
        return out

    def stop(self, char: str, pitch: float) -> list[float]:
        del char, pitch
        return [*self.silence(0.018), *self.noise(0.022, highpass=True), *self.silence(0.012)]

    def silence(self, duration: float) -> list[float]:
        return [0.0] * max(0, int(self.sample_rate * duration))


DIGIT_WORDS = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
}


def envelope(index: int, count: int) -> float:
    if count <= 1:
        return 1.0
    attack = max(1, int(count * 0.18))
    release = max(1, int(count * 0.22))
    if index < attack:
        return index / attack
    if index > count - release:
        return max(0.0, (count - index) / release)
    return 1.0


def append_crossfade(existing: list[float], incoming: list[float], width: int) -> list[float]:
    if not existing or not incoming or width <= 0:
        return existing + incoming
    width = min(width, len(existing), len(incoming))
    out = existing[:-width]
    for index in range(width):
        mix = (index + 1) / (width + 1)
        out.append(existing[-width + index] * (1.0 - mix) + incoming[index] * mix)
    out.extend(incoming[width:])
    return out


def normalize(samples: list[float]) -> list[float]:
    peak = max((abs(sample) for sample in samples), default=0.0)
    if peak <= 0:
        return samples
    scale = 0.82 / peak
    return [sample * scale for sample in samples]


def write_wav(path: Path, samples: list[float], sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        frames = bytearray()
        for sample in samples:
            value = int(max(-1.0, min(1.0, sample)) * 32767)
            frames.extend(struct.pack("<h", value))
        handle.writeframes(bytes(frames))


_generated_store = None


def entrypoint(args, channel, nickname, username, hostname):
    del channel, nickname, username, hostname
    text = " ".join(str(item) for item in args)
    if not text.lower().startswith(("!vocoder ", "vocoder ")):
        text = f"!vocoder {text}"
    for line in render_vocoder_command(text):
        print(line)
