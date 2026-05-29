from __future__ import annotations

import colorsys
import os
import secrets
from pathlib import Path


class GayCommandError(ValueError):
    pass


DEFAULT_SIZE = 800
DEFAULT_FRAMES = 24
DEFAULT_DURATION_MS = 70
DEFAULT_WWW_DIR = "/tmp/pyylmao-www"
DEFAULT_BASE_URL = "http://127.0.0.1:8765"
DEFAULT_BASE_URL_FILE = "/tmp/pyylmao-www-base-url"


def is_gay_command(text: str) -> bool:
    parts = text.strip().split(maxsplit=1)
    return len(parts) == 2 and parts[0].lower() == "!gay" and bool(parts[1].strip())


def render_gay_command(
    text: str,
    *,
    output_dir: str | Path | None = None,
    base_url: str | None = None,
    filename: str | None = None,
    frame_count: int = DEFAULT_FRAMES,
    size: int = DEFAULT_SIZE,
) -> list[str]:
    message = _parse_gay_command(text)
    path, url = _output_path(
        output_dir=output_dir,
        base_url=base_url,
        filename=filename,
    )
    render_gay_gif(message, path, frame_count=frame_count, size=size)
    return [url]


def render_gay_gif(
    text: str,
    path: str | Path,
    *,
    frame_count: int = DEFAULT_FRAMES,
    size: int = DEFAULT_SIZE,
    duration_ms: int = DEFAULT_DURATION_MS,
) -> Path:
    try:
        from PIL import Image, ImageDraw
    except ModuleNotFoundError as exc:
        raise GayCommandError(
            "Pillow is required for !gay GIF rendering. Install with: python3 -m pip install Pillow"
        ) from exc

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = max(2, frame_count)
    size = max(64, size)

    frames = []
    for index in range(frame_count):
        progress = index / frame_count
        background = _rainbow(progress + 0.5)
        foreground = _rainbow(progress)
        image = Image.new("RGB", (size, size), background)
        draw = ImageDraw.Draw(image)
        _draw_centered_text(draw, text, size, foreground)
        frames.append(image)

    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
    )
    return output_path


def _parse_gay_command(text: str) -> str:
    parts = text.strip().split(maxsplit=1)
    if len(parts) != 2 or parts[0].lower() != "!gay" or not parts[1].strip():
        raise GayCommandError("Usage: !gay <text>")
    return parts[1].strip()


def _output_path(
    *,
    output_dir: str | Path | None,
    base_url: str | None,
    filename: str | None,
) -> tuple[Path, str]:
    directory = Path(output_dir or os.getenv("PYYLMAO_WWW_DIR", DEFAULT_WWW_DIR))
    url_base = _base_url(base_url).rstrip("/")
    gif_name = filename or f"gay_{secrets.token_hex(4)}.gif"
    if not gif_name.endswith(".gif"):
        gif_name = f"{gif_name}.gif"
    if "/" in gif_name or "\\" in gif_name:
        raise GayCommandError("Invalid GIF filename")
    return directory / gif_name, f"{url_base}/{gif_name}"


def _base_url(base_url: str | None) -> str:
    if base_url:
        return base_url
    configured = os.getenv("PYYLMAO_WWW_BASE_URL")
    if configured:
        return configured
    url_file = Path(os.getenv("PYYLMAO_WWW_BASE_URL_FILE", DEFAULT_BASE_URL_FILE))
    try:
        discovered = url_file.read_text(encoding="utf-8").strip()
    except OSError:
        discovered = ""
    if discovered.startswith(("http://", "https://")):
        return discovered
    return DEFAULT_BASE_URL


def _rainbow(position: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(position % 1.0, 1.0, 1.0)
    return int(r * 255), int(g * 255), int(b * 255)


def _draw_centered_text(draw, text: str, size: int, fill: tuple[int, int, int]) -> None:
    font, lines = _fit_text(draw, text, size)
    line_heights = [_text_size(draw, line, font)[1] for line in lines]
    spacing = max(4, int(getattr(font, "size", 20) * 0.2))
    total_height = sum(line_heights) + spacing * (len(lines) - 1)
    y = (size - total_height) / 2
    for line, line_height in zip(lines, line_heights):
        width, _ = _text_size(draw, line, font)
        draw.text(((size - width) / 2, y), line, font=font, fill=fill)
        y += line_height + spacing


def _fit_text(draw, text: str, size: int):
    max_width = int(size * 0.9)
    max_height = int(size * 0.82)
    for font_size in range(int(size * 0.2), 11, -2):
        font = _font(font_size)
        lines = _wrap_text(draw, text, font, max_width)
        spacing = max(4, int(font_size * 0.2))
        heights = [_text_size(draw, line, font)[1] for line in lines]
        total_height = sum(heights) + spacing * (len(lines) - 1)
        widest = max((_text_size(draw, line, font)[0] for line in lines), default=0)
        if widest <= max_width and total_height <= max_height:
            return font, lines
    font = _font(12)
    return font, _wrap_text(draw, text, font, max_width)


def _font(size: int):
    try:
        from PIL import ImageFont
    except ModuleNotFoundError as exc:
        raise GayCommandError(
            "Pillow is required for !gay GIF rendering. Install with: python3 -m pip install Pillow"
        ) from exc

    candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    )
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _wrap_text(draw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [text]
    lines: list[str] = []
    current = ""
    for word in words:
        chunks = _break_word(draw, word, font, max_width)
        for chunk in chunks:
            candidate = chunk if not current else f"{current} {chunk}"
            if _text_size(draw, candidate, font)[0] <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = chunk
    if current:
        lines.append(current)
    return lines or [text]


def _break_word(draw, word: str, font, max_width: int) -> list[str]:
    if _text_size(draw, word, font)[0] <= max_width:
        return [word]
    chunks: list[str] = []
    current = ""
    for char in word:
        candidate = current + char
        if current and _text_size(draw, candidate, font)[0] > max_width:
            chunks.append(current)
            current = char
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _text_size(draw, text: str, font) -> tuple[int, int]:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left, bottom - top
