from __future__ import annotations

import math
import shlex
import urllib.request
from dataclasses import dataclass
from io import BytesIO


RGB = tuple[int, int, int]
PixelRows = list[list[RGB]]

RESET_ANSI = "\x1b[0m"
RESET_IRC = "\x0f"
HALF_BLOCK = "▀"

IRC_PALETTE: tuple[RGB, ...] = (
    (255, 255, 255),
    (0, 0, 0),
    (0, 0, 127),
    (0, 147, 0),
    (255, 0, 0),
    (127, 0, 0),
    (156, 0, 156),
    (252, 127, 0),
    (255, 255, 0),
    (0, 252, 0),
    (0, 147, 147),
    (0, 255, 255),
    (0, 0, 252),
    (255, 0, 255),
    (127, 127, 127),
    (210, 210, 210),
)

ANSI_PALETTE: tuple[tuple[int, RGB], ...] = (
    (30, (0, 0, 0)),
    (31, (170, 0, 0)),
    (32, (0, 170, 0)),
    (33, (170, 85, 0)),
    (34, (0, 0, 170)),
    (35, (170, 0, 170)),
    (36, (0, 170, 170)),
    (37, (170, 170, 170)),
    (90, (85, 85, 85)),
    (91, (255, 85, 85)),
    (92, (85, 255, 85)),
    (93, (255, 255, 85)),
    (94, (85, 85, 255)),
    (95, (255, 85, 255)),
    (96, (85, 255, 255)),
    (97, (255, 255, 255)),
)


class Img2IRCError(ValueError):
    pass


@dataclass(frozen=True)
class Img2IRCOptions:
    url: str
    width: int = 60
    render: str = "irc"
    blocks: tuple[str, ...] = ("half", "full")
    contrast: float = 0.0
    brightness: float = 0.0
    saturation: float = 1.0
    gamma: float | None = None
    sharpen: bool = False
    grayscale: bool = False
    max_lines: int = 100
    max_bytes: int = 380


def is_img2irc_command(text: str) -> bool:
    parts = text.strip().split(maxsplit=1)
    return bool(parts and parts[0].lower() in {"!img2irc", "!img2irc2", "!hax"})


def img2irc_trigger_name(text: str) -> str:
    parts = text.strip().split(maxsplit=1)
    if parts and parts[0].lower() == "!hax":
        return "imghax"
    return "img2irc"


def parse_img2irc_command(text: str) -> Img2IRCOptions:
    try:
        tokens = shlex.split(text.strip())
    except ValueError as exc:
        raise Img2IRCError(f"Invalid !img2irc arguments: {exc}") from exc
    if not tokens or tokens[0].lower() not in {"!img2irc", "!img2irc2", "!hax"}:
        raise Img2IRCError("Usage: !img2irc <image-url> [width N] [render irc|ansi|ansi24]")
    if len(tokens) < 2:
        raise Img2IRCError("Usage: !img2irc <image-url> [width N] [render irc|ansi|ansi24]")

    url = tokens[1]
    values: dict[str, object] = {
        "width": 60,
        "render": "irc",
        "blocks": ("half", "full"),
        "contrast": 0.0,
        "brightness": 0.0,
        "saturation": 1.0,
        "gamma": None,
        "sharpen": False,
        "grayscale": False,
    }

    index = 2
    while index < len(tokens):
        token = tokens[index]
        lowered = token.lower()
        if lowered.isdigit():
            values["width"] = int(lowered)
            index += 1
            continue
        if lowered == "+blocks":
            values["blocks"] = ("quarter", "half", "full", "eighth")
            index += 1
            continue
        if lowered == "+sharpen":
            values["sharpen"] = True
            index += 1
            continue
        if lowered in {"+nograyscale", "--no-grayscale"}:
            values["grayscale"] = False
            index += 1
            continue
        if lowered in {"+grayscale", "--grayscale"}:
            values["grayscale"] = True
            index += 1
            continue

        name = lowered[2:] if lowered.startswith("--") else lowered
        if "=" in name:
            name = name.split("=", 1)[0]
        value, index = _option_value(name, token, tokens, index)
        if value is None:
            continue
        _assign_option(values, name.replace("-", "_"), value)

    render = str(values["render"]).lower()
    if render not in {"irc", "ansi", "ansi24"}:
        raise Img2IRCError(f"Unsupported render mode: {render}")
    return Img2IRCOptions(
        url=url,
        width=max(1, min(int(values["width"]), 120)),
        render=render,
        blocks=tuple(values["blocks"]),  # type: ignore[arg-type]
        contrast=float(values["contrast"]),
        brightness=float(values["brightness"]),
        saturation=float(values["saturation"]),
        gamma=values["gamma"],  # type: ignore[arg-type]
        sharpen=bool(values["sharpen"]),
        grayscale=bool(values["grayscale"]),
    )


def render_img2irc_command(text: str) -> list[str]:
    options = parse_img2irc_command(text)
    pixels = load_image_from_url(options.url, options.width, options.max_lines)
    return render_rgb_matrix(pixels, options)


def load_image_from_url(url: str, width: int, max_lines: int = 100) -> PixelRows:
    try:
        from PIL import Image
    except ModuleNotFoundError as exc:
        raise Img2IRCError(
            "Pillow is required for !img2irc URL rendering. Install with: python3 -m pip install Pillow"
        ) from exc

    request = urllib.request.Request(url, headers={"User-Agent": "pyylmao/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = response.read(10_000_001)
    except OSError as exc:
        raise Img2IRCError(f"Could not fetch image: {exc}") from exc
    if len(data) > 10_000_000:
        raise Img2IRCError("Image is too large for !img2irc")

    try:
        with Image.open(BytesIO(data)) as image:
            image = image.convert("RGB")
            src_width, src_height = image.size
            if src_width <= 0 or src_height <= 0:
                raise Img2IRCError("Image has invalid dimensions")
            height = _target_height(src_width, src_height, width, max_lines)
            resampling = getattr(Image, "Resampling", Image).LANCZOS
            image = image.resize((width, height), resampling)
            return [
                [image.getpixel((x, y)) for x in range(image.width)]
                for y in range(image.height)
            ]
    except Img2IRCError:
        raise
    except Exception as exc:
        raise Img2IRCError(f"Could not decode image: {exc}") from exc


def render_rgb_matrix(pixels: PixelRows, options: Img2IRCOptions) -> list[str]:
    if not pixels or not pixels[0]:
        raise Img2IRCError("Image has no pixels")
    resized = resize_matrix(pixels, options.width, options.max_lines)
    adjusted = [
        [_adjust_pixel(pixel, options) for pixel in row]
        for row in resized
    ]
    if options.render == "ansi24":
        return _render_ansi24(adjusted, options.max_bytes)
    if options.render == "ansi":
        return _render_ansi(adjusted, options.max_bytes)
    return _render_irc(adjusted, options.max_bytes)


def resize_matrix(pixels: PixelRows, width: int, max_lines: int = 100) -> PixelRows:
    src_height = len(pixels)
    src_width = len(pixels[0])
    height = _target_height(src_width, src_height, width, max_lines)
    rows: PixelRows = []
    for y in range(height):
        src_y = min(int(y * src_height / height), src_height - 1)
        row: list[RGB] = []
        for x in range(width):
            src_x = min(int(x * src_width / width), src_width - 1)
            row.append(pixels[src_y][src_x])
        rows.append(row)
    return rows


def _render_ansi24(pixels: PixelRows, max_bytes: int) -> list[str]:
    lines: list[str] = []
    for top, bottom in _paired_rows(pixels):
        cells: list[str] = []
        for fg, bg in zip(top, bottom):
            cells.append(
                f"\x1b[38;2;{fg[0]};{fg[1]};{fg[2]}m"
                f"\x1b[48;2;{bg[0]};{bg[1]};{bg[2]}m"
                f"{HALF_BLOCK}"
            )
        lines.extend(_pack_cells(cells, RESET_ANSI, max_bytes))
    return lines


def _render_ansi(pixels: PixelRows, max_bytes: int) -> list[str]:
    lines: list[str] = []
    for top, bottom in _paired_rows(pixels):
        cells: list[str] = []
        for fg, bg in zip(top, bottom):
            fg_code = _nearest_ansi_code(fg)
            bg_code = _ansi_bg_code(_nearest_ansi_code(bg))
            cells.append(f"\x1b[{fg_code};{bg_code}m{HALF_BLOCK}")
        lines.extend(_pack_cells(cells, RESET_ANSI, max_bytes))
    return lines


def _render_irc(pixels: PixelRows, max_bytes: int) -> list[str]:
    lines: list[str] = []
    for top, bottom in _paired_rows(pixels):
        cells: list[str] = []
        for fg, bg in zip(top, bottom):
            cells.append(f"\x03{_nearest_irc(fg):02d},{_nearest_irc(bg):02d}{HALF_BLOCK}")
        lines.extend(_pack_cells(cells, RESET_IRC, max_bytes))
    return lines


def _pack_cells(cells: list[str], reset: str, max_bytes: int) -> list[str]:
    lines: list[str] = []
    parts: list[str] = []
    length = 0
    for cell in cells:
        if parts and length + len(cell) + len(reset) > max_bytes:
            lines.append("".join(parts) + reset)
            parts = []
            length = 0
        parts.append(cell)
        length += len(cell)
    if parts:
        lines.append("".join(parts) + reset)
    return lines


def _paired_rows(pixels: PixelRows) -> list[tuple[list[RGB], list[RGB]]]:
    width = len(pixels[0])
    black = [(0, 0, 0)] * width
    pairs: list[tuple[list[RGB], list[RGB]]] = []
    for index in range(0, len(pixels), 2):
        top = pixels[index]
        bottom = pixels[index + 1] if index + 1 < len(pixels) else black
        pairs.append((top, bottom))
    return pairs


def _option_value(
    name: str,
    token: str,
    tokens: list[str],
    index: int,
) -> tuple[str | None, int]:
    if "=" in token:
        _, value = token.split("=", 1)
        return value, index + 1
    if name in {"width", "render", "blocks", "contrast", "brightness", "saturation", "gamma", "scale", "dither"}:
        if index + 1 >= len(tokens):
            return None, index + 1
        return tokens[index + 1], index + 2
    return None, index + 1


def _assign_option(values: dict[str, object], name: str, value: str) -> None:
    if name in {"width", "w"}:
        values["width"] = _parse_int(value, int(values["width"]))
    elif name == "render":
        values["render"] = value.lower()
    elif name == "blocks":
        values["blocks"] = tuple(
            item.strip().lower()
            for item in value.split(",")
            if item.strip()
        ) or values["blocks"]
    elif name == "contrast":
        values["contrast"] = _parse_float(value, float(values["contrast"]))
    elif name == "brightness":
        values["brightness"] = _parse_float(value, float(values["brightness"]))
    elif name == "saturation":
        values["saturation"] = _parse_saturation(value, float(values["saturation"]))
    elif name == "gamma":
        gamma = _parse_float(value, 0.0)
        values["gamma"] = gamma / 100 if gamma > 10 else gamma


def _parse_int(value: str, default: int) -> int:
    try:
        return int(float(value))
    except ValueError:
        return default


def _parse_float(value: str, default: float) -> float:
    try:
        return float(value)
    except ValueError:
        return default


def _parse_saturation(value: str, default: float) -> float:
    parsed = _parse_float(value, default)
    if parsed > 10:
        return max(0.0, 1.0 + parsed / 100.0)
    return max(0.0, parsed)


def _target_height(src_width: int, src_height: int, width: int, max_lines: int) -> int:
    height = max(1, round(src_height * width / src_width))
    return max(1, min(height, max_lines * 2))


def _adjust_pixel(pixel: RGB, options: Img2IRCOptions) -> RGB:
    red, green, blue = pixel
    if options.grayscale:
        gray = round(0.2126 * red + 0.7152 * green + 0.0722 * blue)
        red = green = blue = gray
    if options.saturation != 1.0:
        gray = 0.2126 * red + 0.7152 * green + 0.0722 * blue
        red = gray + (red - gray) * options.saturation
        green = gray + (green - gray) * options.saturation
        blue = gray + (blue - gray) * options.saturation
    if options.contrast:
        factor = max(0.0, 1.0 + options.contrast / 100.0)
        red = 128 + (red - 128) * factor
        green = 128 + (green - 128) * factor
        blue = 128 + (blue - 128) * factor
    if options.brightness:
        factor = max(0.0, 1.0 + options.brightness / 100.0)
        red *= factor
        green *= factor
        blue *= factor
    if options.gamma and options.gamma > 0:
        red = 255 * math.pow(_clamp(red) / 255, 1 / options.gamma)
        green = 255 * math.pow(_clamp(green) / 255, 1 / options.gamma)
        blue = 255 * math.pow(_clamp(blue) / 255, 1 / options.gamma)
    return (_clamp(red), _clamp(green), _clamp(blue))


def _clamp(value: float) -> int:
    return max(0, min(255, round(value)))


def _nearest_irc(pixel: RGB) -> int:
    return min(range(len(IRC_PALETTE)), key=lambda index: _distance(pixel, IRC_PALETTE[index]))


def _nearest_ansi_code(pixel: RGB) -> int:
    code, _ = min(ANSI_PALETTE, key=lambda item: _distance(pixel, item[1]))
    return code


def _ansi_bg_code(fg_code: int) -> int:
    if 30 <= fg_code <= 37:
        return fg_code + 10
    return fg_code + 10


def _distance(left: RGB, right: RGB) -> int:
    return (
        (left[0] - right[0]) ** 2
        + (left[1] - right[1]) ** 2
        + (left[2] - right[2]) ** 2
    )
