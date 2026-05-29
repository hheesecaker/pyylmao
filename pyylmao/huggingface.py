from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


class HuggingFaceCommandError(Exception):
    pass


@dataclass(frozen=True)
class HFModel:
    repo_id: str
    created_at: str

    @property
    def created_date(self) -> str:
        try:
            return datetime.fromisoformat(self.created_at.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            return datetime.now(timezone.utc).date().isoformat()


class HFTrendingProvider(Protocol):
    def trending(self, limit: int = 10) -> list[HFModel]:
        ...


class HuggingFaceAPITrendingProvider:
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def trending(self, limit: int = 10) -> list[HFModel]:
        query = urllib.parse.urlencode({"limit": str(limit)})
        url = f"https://huggingface.co/api/models?{query}"
        request = urllib.request.Request(url, headers={"User-Agent": "pyylmao/0.1"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        models = []
        for item in payload:
            repo_id = str(item.get("modelId") or item.get("id") or "")
            if not repo_id or "/" not in repo_id:
                continue
            created_at = str(item.get("createdAt") or item.get("lastModified") or "")
            models.append(HFModel(repo_id=repo_id, created_at=created_at))
        if not models:
            raise HuggingFaceCommandError("No Hugging Face trending models found.")
        return models[:limit]


def render_hf_command(
    text: str,
    provider: HFTrendingProvider | None = None,
    limit: int = 10,
) -> list[str]:
    if text.strip().lower() != "!hf":
        return ["Usage: !hf"]
    provider = provider or HuggingFaceAPITrendingProvider()
    try:
        models = provider.trending(limit)
    except HuggingFaceCommandError:
        raise
    except Exception as exc:
        raise HuggingFaceCommandError(f"HF error: {exc}") from exc
    width = max(len(model.repo_id) for model in models)
    lines = ["HF Trending (Last 1 Days):"]
    for model in models:
        lines.append(
            f" ★ {model.created_date}  {model.repo_id:<{width}}  https://huggingface.co/{model.repo_id}"
        )
    return lines
