from __future__ import annotations

import re
from typing import Any

import llm
from pyylmao.kv import kv_delete, kv_get, kv_query, kv_set


pattern = r"^(.*(https?://[^ ]+).*)$"

URL_RE = re.compile(r"https?://[^ ]+")
DEFAULT_MODEL = "openrouter/openai/gpt-oss-120b"
DEFAULT_PROMPT = "Describe this image briefly for IRC."
DEFAULT_SYSTEM = ""
DEFAULT_TEMPERATURE = 0.2


def _first_url(text: str) -> str:
    match = URL_RE.search(text)
    return match.group(0) if match else ""


def _kv(path: str, default: Any) -> Any:
    try:
        return kv_get(path, default)
    except Exception:
        return default


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _args_text(args: list[str] | tuple[str, ...] | str) -> str:
    if isinstance(args, str):
        return args
    url_args = [str(item) for item in args if _first_url(str(item))]
    if url_args:
        return url_args[-1]
    return " ".join(str(item) for item in args)


def render_imgcap_command(text: str) -> list[str]:
    url = _first_url(text)
    if not url:
        return []

    model_name = str(_kv("commands.imgcap.model", DEFAULT_MODEL))
    prompt = str(_kv("commands.imgcap.prompt", DEFAULT_PROMPT))
    system = str(_kv("commands.imgcap.system", DEFAULT_SYSTEM))
    attachment_type = str(_kv("commands.imgcap.attachment_type", "image/png"))
    temperature = _float(_kv("commands.imgcap.temperature", DEFAULT_TEMPERATURE), DEFAULT_TEMPERATURE)

    model = llm.get_model(model_name)
    image = llm.Attachment(url=url, type=attachment_type)
    response = model.prompt(
        prompt,
        attachments=[image],
        system=system,
        options={"temperature": temperature},
    )

    _ignore_errors(lambda: kv_set("commands.imgcap.last_url", url))
    caption = response.text()
    return [line for line in caption.splitlines() if line.strip()]


def _ignore_errors(callback):
    try:
        return callback()
    except Exception:
        return None


def entrypoint(args, channel, nickname, username, hostname):
    del channel, nickname, username, hostname
    for line in render_imgcap_command(_args_text(args)):
        print(line)
