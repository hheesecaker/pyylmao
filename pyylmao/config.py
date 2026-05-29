from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


BASE_DIR = Path(os.getenv("PYYLMAO_BASE_DIR", Path.cwd())).resolve()
ASSETS_DIR = Path(os.getenv("PYYLMAO_ASSETS_DIR", BASE_DIR / "assets")).resolve()
DATA_DIR = Path(os.getenv("PYYLMAO_DATA_DIR", BASE_DIR / "data")).resolve()


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv_env(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class BotConfig:
    server: str = "irc.notgay.men"
    port: int = 6667
    tls: bool = False
    nick: str = "pyylmao"
    username: str = "pyylmao"
    realname: str = "pyylmao"
    channels: list[str] = field(default_factory=lambda: ["#not-gay"])
    password: str | None = None
    openrouter_api_key: str | None = None
    default_model: str = "openai/gpt-oss-120b"
    grok_model: str = "x-ai/grok-4.1-fast"
    state_path: Path = Path("data/pyylmao-state.json")
    ascii_art_dir: Path | None = None
    cat_dir: Path | None = None
    mdcat_dir: Path | None = None
    preview_urls: bool = True
    respond_to_llm_triggers: bool = True
    line_delay_seconds: float = 0.8
    max_irc_line: int = 390
    bluesky_poll_seconds: float = 60.0
    bluesky_search_limit: int = 25

    @classmethod
    def from_env(cls) -> "BotConfig":
        return cls(
            server=os.getenv("PYYLMAO_SERVER", cls.server),
            port=int(os.getenv("PYYLMAO_PORT", str(cls.port))),
            tls=_bool_env("PYYLMAO_TLS", cls.tls),
            nick=os.getenv("PYYLMAO_NICK", cls.nick),
            username=os.getenv("PYYLMAO_USERNAME", cls.username),
            realname=os.getenv("PYYLMAO_REALNAME", cls.realname),
            channels=_csv_env("PYYLMAO_CHANNELS", "#not-gay"),
            password=os.getenv("PYYLMAO_PASSWORD"),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
            default_model=os.getenv("PYYLMAO_DEFAULT_MODEL", cls.default_model),
            grok_model=os.getenv("PYYLMAO_GROK_MODEL", cls.grok_model),
            state_path=Path(os.getenv("PYYLMAO_STATE", str(cls.state_path))),
            ascii_art_dir=(
                Path(os.environ["PYYLMAO_ASCII_DIR"])
                if os.getenv("PYYLMAO_ASCII_DIR")
                else None
            ),
            cat_dir=(
                Path(os.environ["PYYLMAO_CAT_DIR"])
                if os.getenv("PYYLMAO_CAT_DIR")
                else None
            ),
            mdcat_dir=(
                Path(os.environ["PYYLMAO_MDCAT_DIR"])
                if os.getenv("PYYLMAO_MDCAT_DIR")
                else None
            ),
            preview_urls=_bool_env("PYYLMAO_PREVIEW_URLS", cls.preview_urls),
            respond_to_llm_triggers=_bool_env(
                "PYYLMAO_LLM_TRIGGERS", cls.respond_to_llm_triggers
            ),
            line_delay_seconds=float(
                os.getenv("PYYLMAO_LINE_DELAY_SECONDS", str(cls.line_delay_seconds))
            ),
            max_irc_line=int(os.getenv("PYYLMAO_MAX_IRC_LINE", str(cls.max_irc_line))),
            bluesky_poll_seconds=float(
                os.getenv("PYYLMAO_BSKY_POLL_SECONDS", str(cls.bluesky_poll_seconds))
            ),
            bluesky_search_limit=int(
                os.getenv("PYYLMAO_BSKY_SEARCH_LIMIT", str(cls.bluesky_search_limit))
            ),
        )
