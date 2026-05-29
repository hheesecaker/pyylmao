from __future__ import annotations

import json
import base64
import mimetypes
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Callable
from urllib.parse import urlencode

from .llm_tools import ToolExecutor, format_tool_args, parse_tool_arguments


SYSTEM_PROMPT = """You are pyylmao, a concise IRC bot. Answer directly and keep IRC replies short.

Use tools when the user asks you to inspect bot commands, debug command behavior, inspect chat history, manage skills, store memories, save artifacts, or create/update commands.

When creating or editing generated commands, use write_command with name, pattern, code, and optional content. Put executable Python only in code; content is a short human description.

Preferred generated command API:
import llm
class Tool(llm.Toolbox):
    pattern = r'^!name(?:\\s+(.+))?$'
    def __init__(self, args, event, connection):
        self.args = args
        self.event = event
        self.connection = connection
    def _onload(self):
        print('reply text')

Legacy API also works:
pattern = r'^!name(?:\\s+(.+))?$'
def entrypoint(args, channel, nickname, username, hostname):
    print(args[0] if args else 'reply text')

Printed output, returned strings, and returned lists become IRC reply lines. Use read_command before changing an existing command. Use run with cmd_name and args to test generated or reconstructed commands; use shell command only for low-level debugging."""


CANCELLED_TOOL_RESULT = "Tool calls cancelled: user intervention"
DEFAULT_MAX_TOOL_ROUNDS = 32
DEFAULT_MAX_TIME_SECONDS = 600


@dataclass(frozen=True)
class LLMResult:
    lines: list[str]
    elapsed: float
    prompt_tokens: int | None
    completion_tokens: int | None
    model: str
    tool_traces: tuple[str, ...] = ()
    request_count: int = 1
    cost_usd: Decimal | None = None
    total_cost_usd: Decimal | None = None


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        app_name: str = "pyylmao",
        transport: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        clock: Callable[[], float] | None = None,
        monotonic: Callable[[], float] | None = None,
    ):
        self.api_key = api_key
        self.app_name = app_name
        self.transport = transport
        self.clock = clock or time.time
        self.monotonic = monotonic or time.perf_counter
        self._total_cost_usd = Decimal("0")
        self._total_cost_lock = threading.Lock()

    def chat(
        self,
        prompt: str,
        model: str,
        tools: ToolExecutor | None = None,
        max_tool_rounds: int = DEFAULT_MAX_TOOL_ROUNDS,
        max_time_seconds: int | None = DEFAULT_MAX_TIME_SECONDS,
        temperature: float | None = None,
        extra_system: str = "",
        attachments: list[Any] | None = None,
        cancel_checker: Callable[[], bool] | None = None,
    ) -> LLMResult:
        started = self.monotonic()
        started_wall = int(self.clock())
        system_prompt = SYSTEM_PROMPT
        if extra_system:
            system_prompt += "\n\nUser system prompt:\n" + extra_system
        user_content: str | list[dict[str, Any]]
        if attachments:
            user_content = [{"type": "text", "text": prompt}]
            user_content.extend(attachment_content_parts(attachments))
        else:
            user_content = prompt
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": system_prompt,
            },
            {"role": "user", "content": user_content},
        ]
        tool_traces: list[str] = []
        prompt_tokens = 0
        completion_tokens = 0
        request_count = 0
        cost_usd = Decimal("0")
        generation_ids: list[str] = []
        final_model = model

        def finish(lines: list[str]) -> LLMResult:
            nonlocal cost_usd
            elapsed = self.monotonic() - started
            if generation_ids:
                cost_usd += self._generation_cost_usd(generation_ids)
            total_cost_usd = None
            result_cost_usd = cost_usd if cost_usd else None
            if result_cost_usd is not None:
                with self._total_cost_lock:
                    self._total_cost_usd += result_cost_usd
                    total_cost_usd = self._total_cost_usd
            return LLMResult(
                lines=lines,
                elapsed=elapsed,
                prompt_tokens=prompt_tokens or None,
                completion_tokens=completion_tokens or None,
                model=final_model,
                tool_traces=tuple(tool_traces),
                request_count=request_count,
                cost_usd=result_cost_usd,
                total_cost_usd=total_cost_usd,
            )

        tool_rounds = 0
        while True:
            payload: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": 0.7 if temperature is None else temperature,
            }
            if tools is not None:
                payload["tools"] = tools.schemas()
                payload["tool_choice"] = "auto"
                payload["parallel_tool_calls"] = False
            data = self._post_chat(payload)
            request_count += 1
            usage = data.get("usage") or {}
            prompt_tokens += int(usage.get("prompt_tokens") or 0)
            completion_tokens += int(usage.get("completion_tokens") or 0)
            request_cost_usd = response_cost_usd(data)
            if request_cost_usd is None:
                generation_id = data.get("id")
                if generation_id:
                    generation_ids.append(str(generation_id))
            else:
                cost_usd += request_cost_usd
            final_model = data.get("model") or final_model
            message = data["choices"][0]["message"]
            tool_calls = message.get("tool_calls") or []
            if tools is None or not tool_calls:
                content = normalize_content(message.get("content", "")).strip()
                return finish(content.splitlines() or [content])
            if tool_rounds >= max_tool_rounds:
                return finish([f"Chain limit of {max_tool_rounds} exceeded."])
            tool_rounds += 1
            messages.append(
                {
                    "role": "assistant",
                    "content": normalize_content(message.get("content", "")),
                    "tool_calls": tool_calls,
                }
            )
            for call in tool_calls:
                function = call.get("function") or {}
                name = function.get("name") or ""
                arguments = parse_tool_arguments(function.get("arguments"))
                cancelled_result = tool_cancellation_result(
                    cancel_checker,
                    max_time_seconds,
                    started_wall,
                    self.clock,
                    tool_traces,
                )
                if cancelled_result:
                    result = cancelled_result
                    tool_traces.append(result)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.get("id", name),
                            "name": name,
                            "content": result,
                        }
                    )
                    continue
                tool_traces.append(f"{name} args: {format_tool_args(arguments)}")
                try:
                    result = tools.execute(name, arguments)
                except Exception as exc:
                    result = f"tool error: {exc}"
                result_trace = tool_result_trace(name, result)
                if result_trace:
                    tool_traces.append(result_trace)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id", name),
                        "name": name,
                        "content": result,
                    }
                )
    def _post_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.transport is not None:
            return self.transport(payload)
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://localhost/pyylmao",
                "X-Title": self.app_name,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenRouter HTTP {exc.code}: {detail[:300]}") from exc
        return json.loads(raw)

    def _generation_cost_usd(self, generation_ids: list[str]) -> Decimal:
        if self.transport is not None:
            return Decimal("0")
        total = Decimal("0")
        for generation_id in generation_ids:
            cost = self._fetch_generation_cost_usd(generation_id)
            if cost is not None:
                total += cost
        return total

    def _fetch_generation_cost_usd(self, generation_id: str) -> Decimal | None:
        query = urlencode({"id": generation_id})
        request = urllib.request.Request(
            f"https://openrouter.ai/api/v1/generation?{query}",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "User-Agent": "pyylmao/0.1",
            },
        )
        for attempt in range(5):
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except (OSError, urllib.error.HTTPError, json.JSONDecodeError):
                if attempt == 4:
                    return None
                time.sleep(0.4)
                continue
            cost = response_cost_usd(payload)
            if cost is not None:
                return cost
            if attempt != 4:
                time.sleep(0.4)
        return None


def attachment_content_parts(attachments: list[Any]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for attachment in attachments:
        url = attachment_url(attachment)
        content_type = attachment_type(attachment, url)
        if url:
            parts.append({"type": "image_url", "image_url": {"url": url}})
            continue
        data = attachment_bytes(attachment)
        if data is None:
            continue
        data_url = "data:" + content_type + ";base64," + base64.b64encode(data).decode("ascii")
        parts.append({"type": "image_url", "image_url": {"url": data_url}})
    return parts


def attachment_url(attachment: Any) -> str:
    if isinstance(attachment, dict):
        value = attachment.get("url")
    else:
        value = getattr(attachment, "url", None)
    return "" if value is None else str(value)


def attachment_type(attachment: Any, url: str = "") -> str:
    if isinstance(attachment, dict):
        value = attachment.get("type") or attachment.get("content_type")
        path = attachment.get("path")
    else:
        value = (
            getattr(attachment, "type", None)
            or getattr(attachment, "content_type", None)
            or getattr(attachment, "media_type", None)
        )
        path = getattr(attachment, "path", None)
    if value:
        return str(value)
    guessed, _ = mimetypes.guess_type(str(path or url))
    return guessed or "image/png"


def attachment_bytes(attachment: Any) -> bytes | None:
    if isinstance(attachment, dict):
        content = attachment.get("content")
        path = attachment.get("path")
    else:
        content = getattr(attachment, "content", None)
        path = getattr(attachment, "path", None)
        content_bytes = getattr(attachment, "content_bytes", None)
        if callable(content_bytes):
            value = content_bytes()
            if isinstance(value, bytes):
                return value
            if isinstance(value, str):
                return value.encode("utf-8")
    if content is not None:
        if isinstance(content, bytes):
            return content
        if isinstance(content, str):
            return content.encode("utf-8")
    if path:
        with open(str(path), "rb") as handle:
            return handle.read()
    return None


VALUE_COLOR = "\x03" "94"
LABEL_COLOR = "\x03" "93"

MONOSPACE_MAP = str.maketrans(
    "abcdefghijklmnopqrstuvwxyz123456789",
    "𝚊𝚋𝚌𝚍𝚎𝚏𝚐𝚑𝚒𝚓𝚔𝚕𝚖𝚗𝚘𝚙𝚚𝚛𝚜𝚝𝚞𝚟𝚠𝚡𝚢𝚣𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿",
)


def stats_line(result: LLMResult) -> str:
    left = "?" if result.prompt_tokens is None else str(result.prompt_tokens)
    right = "?" if result.completion_tokens is None else str(result.completion_tokens)
    parts: list[str] = []
    if result.request_count > 1:
        parts.append(f"{VALUE_COLOR}{result.request_count} {LABEL_COLOR}𝘳𝘦𝘲")
    parts.extend(
        [
            f"{VALUE_COLOR}{result.elapsed:.1f} {LABEL_COLOR}𝘴𝘦𝘤",
            f"{VALUE_COLOR}{left} {LABEL_COLOR}🢃",
            f"{VALUE_COLOR}{right} {LABEL_COLOR}🡹",
        ]
    )
    if result.cost_usd is not None:
        total_cost_usd = result.total_cost_usd or result.cost_usd
        parts.extend(
            [
                f"{VALUE_COLOR}{format_cents(result.cost_usd)}¢ {LABEL_COLOR}━",
                f"{VALUE_COLOR}{format_cents(total_cost_usd)}¢ {LABEL_COLOR}㍰",
            ]
        )
    parts.append(f"{VALUE_COLOR}{format_model_name(result.model)} {LABEL_COLOR}𝚘𝚙𝚎𝚗𝚛𝚘𝚞𝚝𝚎𝚛")
    return " ‖ ".join(parts)


def response_cost_usd(payload: dict[str, Any]) -> Decimal | None:
    usage = payload.get("usage")
    if isinstance(usage, dict):
        cost = decimal_cost(usage.get("cost"))
        if cost is not None:
            return cost
        cost = decimal_cost(usage.get("total_cost"))
        if cost is not None:
            return cost
    for key in ("cost", "total_cost", "cost_usd", "total_cost_usd"):
        cost = decimal_cost(payload.get(key))
        if cost is not None:
            return cost
    data = payload.get("data")
    if isinstance(data, dict):
        return response_cost_usd(data)
    return None


def decimal_cost(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite() or amount < 0:
        return None
    return amount


def format_cents(value_usd: Decimal | float | int) -> str:
    cents = Decimal(str(value_usd)) * Decimal("100")
    rounded = cents.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    text = format(rounded, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def format_model_name(model: str) -> str:
    return model.lower().translate(MONOSPACE_MAP)


def normalize_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        pieces = []
        for item in content:
            if isinstance(item, dict):
                pieces.append(str(item.get("text") or item.get("content") or ""))
            else:
                pieces.append(str(item))
        return "\n".join(piece for piece in pieces if piece)
    return "" if content is None else str(content)


def tool_result_trace(name: str, result: str) -> str:
    if name == "get_chat_history":
        label = getattr(result, "trace_label", "after filter") or "after filter"
        if not result or result == "No chat history available.":
            return f"read 0 lines {label}"
        return f"read {len(result.splitlines())} lines {label}"
    if name == "semantic_search":
        first_line = result.splitlines()[0] if result else ""
        return first_line if first_line.startswith("Profile: ") else ""
    if name in {"write_command", "revise_pattern", "run", "save_artifact", "irc_command"}:
        return visible_tool_result(result)
    return ""


def tool_cancelled(cancel_checker: Callable[[], bool] | None) -> bool:
    if cancel_checker is None:
        return False
    try:
        return bool(cancel_checker())
    except Exception:
        return False


def tool_cancellation_result(
    cancel_checker: Callable[[], bool] | None,
    max_time_seconds: int | None,
    started_wall: int,
    clock: Callable[[], float],
    traces: list[str],
) -> str:
    if tool_cancelled(cancel_checker):
        return CANCELLED_TOOL_RESULT
    if max_time_seconds is None:
        return ""
    now = clock()
    if now - started_wall < max_time_seconds:
        return ""
    traces.append(f"max_time reached: {now} {started_wall} {max_time_seconds}")
    return f"Tool calls cancelled: max_time {max_time_seconds}s reached"


def visible_tool_result(result: str, limit: int = 4000) -> str:
    if not result:
        return ""
    if len(result) <= limit:
        return result
    return result[:limit] + "\n... truncated ..."
