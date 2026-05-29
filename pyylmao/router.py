from __future__ import annotations

import asyncio
import inspect
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Awaitable, Callable

from .aliases import DEFAULT_ALIASES, AliasStore, normalize_model_id
from .ansi2irc import Ansi2IRCError, is_ansi2irc_command, render_ansi2irc_command
from .ascii_art import AsciiArtStore
from .blair import (
    BlairCommandError,
    is_blair2_command,
    is_blair_command,
    render_blair2_command,
    render_blair_command,
)
from .bluesky import BlueskyFeedWatcher
from .cat import is_cat_command, render_cat_command
from .chkdomain import is_chkdomain_command, render_chkdomain_command
from .chess_game import ChessStore, is_chess_command
from .command_list import render_command_table
from .cowsay import is_cowsay_command, render_cowsay_command
from .cp import CryptoPriceError, is_cp_command, render_cp_command
from .crt import is_crt_command, render_crt_command
from .curl import CurlCommandError, is_curl_command, render_curl_command
from .define import DefineCommandError, is_define_command, render_define_command
from .echo import is_echo_command, render_echo_command
from .eval_command import is_eval_command, render_eval_command
from .figlet import is_figlet_command, render_figlet_command
from .filters import FilterStore
from .formatting import clean_nick, split_irc_lines
from .fortune import is_fortune_command, render_fortune_command
from .gay import GayCommandError, is_gay_command, render_gay_command
from .generated_commands import GeneratedCommandStore, MessageEvent
from .godsays import is_godsays_command, render_godsays_command
from .golem import GolemControlStore, is_golem_control_command
from .history_store import BOT_NICK, clear_channel_history, record_history
from .huggingface import HuggingFaceCommandError, render_hf_command
from .horoscope import is_horoscope_command, render_horoscope_command
from .host import is_host_command, render_host_command
from .img2irc import Img2IRCError, img2irc_trigger_name, is_img2irc_command, render_img2irc_command
from .imdb import ImdbCommandError, is_imdb_command, render_imdb_command
from .invite import is_invite_command, render_invite_command
from .kvstore import KVStore, is_kv_command
from .link_preview import first_url, is_youtube_url, preview_title
from .light import is_light_command, render_light_command
from .ligma import LigmaCommandError, is_ligma_command, render_ligma_command
from .livebench import is_livebench_command, render_livebench_command
from .llm import OpenRouterClient, stats_line
from .llm_tools import LLMToolContext, LLMToolRegistry
from .llm_prices import LLMPricesError, is_llm_prices_command, render_llm_prices_command
from .mdcat import is_mdcat_command, render_mdcat_command
from .models import ModelsCommandError, is_models_command, render_models_command
from .nostr import NostrCommandError, is_nostr_command, render_nostr_command
from .palette import is_palette99_command, render_palette99
from .phenoguessr import PhenoguessrStore, is_phenoguessr_command
from .poll import PollStore, is_poll_command
from .radio import RadioStore, is_radio_help_command, render_radio_help
from .random_command import is_random_command, render_random_command
from .reload_command import is_reload_command, render_reload_command
from .reminders import ReminderStore, is_reminder_command
from .seen import is_seen_command, render_seen_command
from .stocks import StockCommandError, render_stock_command
from .summary import SummaryError, is_summary_command, run_summary_command
from .test_command import is_test_command, render_test_command
from .todo import TodoStore, is_todo_command
from .tools_table import handle_tool_toggle, render_tools_table
from .trivia import TriviaStore, is_trivia_command
from .triggers import TriggerStore
from .twitter import TwitterCommandError, is_twitter_command, render_twitter_command
from .ufc import UFCCommandError, is_ufc_command, render_ufc_command
from .urbandict import UrbanDictCommandError, is_urban_command, render_urban_command
from .vocoder import VocoderCommandError, is_vocoder_command, render_vocoder_command
from .vtrade import VTrade
from .weather import WeatherCommandError, WeatherRenderers, default_weather_renderers
from .ytsearch import YTSearchError, is_ytsearch_command, render_ytsearch_command
from .zscore import is_zscore_command, render_zscore_command


LLM_TRIGGERS = (
    ("@@grok", "grok"),
    ("@grok", "grok"),
    ("grok,", "grok"),
    ("grok:", "grok"),
    ("@@gpt", "gpt"),
    ("@gpt", "gpt"),
    ("gpt,", "gpt"),
    ("gpt:", "gpt"),
)


@dataclass(frozen=True)
class RoutedReply:
    lines: list[str]
    async_task: bool = False


@dataclass
class TaskInfo:
    task: asyncio.Task
    label: str
    target: str
    started_at: float


@dataclass(frozen=True)
class LLMOptions:
    max_history: int | None = None
    temperature: float | None = None
    system: str = ""


class RunningCommands:
    def __init__(self):
        self.next_id = 1
        self.tasks: dict[int, TaskInfo] = {}

    def add(self, task: asyncio.Task, label: str, target: str) -> int:
        task_id = self.next_id
        self.next_id += 1
        self.tasks[task_id] = TaskInfo(
            task=task,
            label=label,
            target=target,
            started_at=time.time(),
        )
        task.add_done_callback(lambda _: self.tasks.pop(task_id, None))
        return task_id

    def kill_all(self) -> list[int]:
        ids = list(self.tasks)
        for info in list(self.tasks.values()):
            info.task.cancel()
        return ids

    def kill(self, task_id: int) -> bool:
        info = self.tasks.get(task_id)
        if info is None:
            return False
        info.task.cancel()
        return True

    def list(self) -> list[str]:
        if not self.tasks:
            return []
        now = time.time()
        lines = ["Running commands:"]
        for task_id, info in sorted(self.tasks.items()):
            elapsed = int(now - info.started_at)
            lines.append(f"#{task_id} {info.label} on {info.target} t={elapsed}s")
        return lines


LLM_TOOL_CANCELLATION_KEY = "llm_tool_cancellation_flag"


def toggle_llm_tool_cancellation(state) -> bool:
    new_value = not bool(state.data.get(LLM_TOOL_CANCELLATION_KEY))
    state.data[LLM_TOOL_CANCELLATION_KEY] = new_value
    state.save()
    return new_value


def callable_accepts_keyword(callable_obj, name: str) -> bool:
    try:
        signature = inspect.signature(callable_obj)
    except (TypeError, ValueError):
        return False
    for parameter in signature.parameters.values():
        if parameter.kind == inspect.Parameter.VAR_KEYWORD:
            return True
        if parameter.name == name:
            return True
    return False


class Router:
    def __init__(
        self,
        vtrade: VTrade,
        filters: FilterStore,
        llm_client: OpenRouterClient | None,
        default_model: str,
        grok_model: str,
        preview_urls_enabled: bool = True,
        llm_triggers_enabled: bool = True,
        max_irc_line: int = 390,
        ansi2irc_renderer: Callable[[str], list[str]] | None = None,
        image_renderer: Callable[[str], list[str]] | None = None,
        ascii_art: AsciiArtStore | None = None,
        blair_renderer: Callable[[str], list[str]] | None = None,
        blair2_renderer: Callable[[str], list[str]] | None = None,
        hf_renderer: Callable[[str], list[str]] | None = None,
        stock_renderer: Callable[[str], list[str]] | None = None,
        zscore_renderer: Callable[[str], list[str]] | None = None,
        echo_renderer: Callable[[str], list[str]] | None = None,
        cowsay_renderer: Callable[[str], list[str]] | None = None,
        test_renderer: Callable[[str], list[str]] | None = None,
        fortune_renderer: Callable[[str], list[str]] | None = None,
        gay_renderer: Callable[[str], list[str]] | None = None,
        godsays_renderer: Callable[[str], list[str]] | None = None,
        urban_renderer: Callable[[str], list[str]] | None = None,
        define_renderer: Callable[[str], list[str]] | None = None,
        cp_renderer: Callable[[str], list[str]] | None = None,
        curl_renderer: Callable[[str], list[str]] | None = None,
        cat_renderer: Callable[[str], list[str]] | None = None,
        mdcat_renderer: Callable[[str], list[str]] | None = None,
        figlet_renderer: Callable[[str], list[str]] | None = None,
        light_renderer: Callable[[str], list[str]] | None = None,
        livebench_renderer: Callable[[str], list[str]] | None = None,
        ligma_renderer: Callable[[str], list[str]] | None = None,
        nostr_renderer: Callable[[str], list[str]] | None = None,
        twitter_renderer: Callable[[str], list[str]] | None = None,
        ufc_renderer: Callable[[str], list[str]] | None = None,
        imdb_renderer: Callable[[str], list[str]] | None = None,
        vocoder_renderer: Callable[[str], list[str]] | None = None,
        llm_prices_renderer: Callable[[str], list[str]] | None = None,
        models_renderer: Callable[[str], list[str]] | None = None,
        chkdomain_renderer: Callable[[str], list[str]] | None = None,
        host_renderer: Callable[[str], list[str]] | None = None,
        crt_renderer: Callable[[str, str | None], list[str]] | None = None,
        horoscope_renderer: Callable[[str, str], list[str]] | None = None,
        ytsearch_renderer: Callable[[str], list[str]] | None = None,
        invite_renderer: Callable[[str], list[str]] | None = None,
        random_renderer: Callable[[str], list[str]] | None = None,
        reminders: ReminderStore | None = None,
        todos: TodoStore | None = None,
        chess: ChessStore | None = None,
        polls: PollStore | None = None,
        phenoguessr: PhenoguessrStore | None = None,
        radio: RadioStore | None = None,
        trivia: TriviaStore | None = None,
        kvstore: KVStore | None = None,
        triggers: TriggerStore | None = None,
        golem: GolemControlStore | None = None,
        aliases: AliasStore | None = None,
        llm_tools: LLMToolRegistry | None = None,
        raw_irc_sender: Callable[[list[str]], str] | None = None,
        generated_commands: GeneratedCommandStore | None = None,
        weather_renderers: WeatherRenderers | None = None,
        summary_runner: Callable[[str, str | None], list[str]] | None = None,
        bluesky_runner: Callable[
            [Callable[[str, list[str]], Awaitable[None]], str], Awaitable[None]
        ]
        | None = None,
        bluesky_poll_seconds: float = 60.0,
        bluesky_search_limit: int = 25,
    ):
        self.vtrade = vtrade
        self.filters = filters
        self.ascii_art = ascii_art or AsciiArtStore.default()
        self.llm_client = llm_client
        self.default_model = default_model
        self.grok_model = grok_model
        self.preview_urls_enabled = preview_urls_enabled
        self.llm_triggers_enabled = llm_triggers_enabled
        self.max_irc_line = max_irc_line
        self.ansi2irc_renderer = ansi2irc_renderer or render_ansi2irc_command
        self.image_renderer = image_renderer or render_img2irc_command
        self.blair_renderer = blair_renderer or render_blair_command
        self.blair2_renderer = blair2_renderer or render_blair2_command
        self.hf_renderer = hf_renderer or render_hf_command
        self.stock_renderer = stock_renderer or render_stock_command
        self.zscore_renderer = zscore_renderer or render_zscore_command
        self.echo_renderer = echo_renderer or render_echo_command
        self.cowsay_renderer = cowsay_renderer or render_cowsay_command
        self.test_renderer = test_renderer or render_test_command
        self.fortune_renderer = fortune_renderer or render_fortune_command
        self.gay_renderer = gay_renderer or render_gay_command
        self.godsays_renderer = godsays_renderer or render_godsays_command
        self.urban_renderer = urban_renderer or render_urban_command
        self.define_renderer = define_renderer or render_define_command
        self.cp_renderer = cp_renderer or render_cp_command
        self.curl_renderer = curl_renderer or render_curl_command
        self.cat_renderer = cat_renderer or render_cat_command
        self.mdcat_renderer = mdcat_renderer or render_mdcat_command
        self.figlet_renderer = figlet_renderer or render_figlet_command
        self.light_renderer = light_renderer or render_light_command
        self.livebench_renderer = livebench_renderer or render_livebench_command
        self.ligma_renderer = ligma_renderer or render_ligma_command
        self.nostr_renderer = nostr_renderer or render_nostr_command
        self.twitter_renderer = twitter_renderer or render_twitter_command
        self.ufc_renderer = ufc_renderer or render_ufc_command
        self.imdb_renderer = imdb_renderer or render_imdb_command
        self.vocoder_renderer = vocoder_renderer or render_vocoder_command
        self.llm_prices_renderer = llm_prices_renderer or render_llm_prices_command
        self.models_renderer = models_renderer or render_models_command
        self.chkdomain_renderer = chkdomain_renderer or render_chkdomain_command
        self.host_renderer = host_renderer or render_host_command
        self.crt_renderer = crt_renderer or render_crt_command
        self.horoscope_renderer = horoscope_renderer or render_horoscope_command
        self.ytsearch_renderer = ytsearch_renderer or render_ytsearch_command
        self.invite_renderer = invite_renderer or (
            lambda text: render_invite_command(text, raw_irc_sender)
        )
        self.random_renderer = random_renderer or render_random_command
        self.reminders = reminders or ReminderStore(filters.state)
        self.todos = todos or TodoStore(filters.state)
        self.chess = chess or ChessStore(filters.state)
        self.polls = polls or PollStore(filters.state)
        self.phenoguessr = phenoguessr or PhenoguessrStore(
            filters.state,
            image_renderer=self.image_renderer,
        )
        self.radio = radio or RadioStore(filters.state)
        self.trivia = trivia or TriviaStore(filters.state)
        self.kvstore = kvstore or KVStore(filters.state)
        self.triggers = triggers or TriggerStore(filters.state)
        self.golem = golem or GolemControlStore(filters.state)
        alias_defaults = {
            **DEFAULT_ALIASES,
            "gpt": f"openrouter/{self.default_model}",
            "grok": f"openrouter/{self.grok_model}",
            "pyylmao": f"openrouter/{self.grok_model}",
        }
        self.aliases = aliases or AliasStore(
            filters.state,
            defaults=alias_defaults,
        )
        self.llm_tools = llm_tools or LLMToolRegistry(
            filters.state,
            raw_irc_sender=raw_irc_sender,
            command_runner=self.run_llm_tool_command,
        )
        self.generated_commands = generated_commands or GeneratedCommandStore(
            filters.state,
            raw_irc_sender=raw_irc_sender,
        )
        self.weather_renderers = weather_renderers or default_weather_renderers()
        self.summary_runner = summary_runner
        self.bluesky_runner = bluesky_runner
        self.bluesky_poll_seconds = bluesky_poll_seconds
        self.bluesky_search_limit = bluesky_search_limit
        self.running = RunningCommands()
        self.history: dict[str, deque[tuple[str, str]]] = defaultdict(lambda: deque(maxlen=500))
        self.history_limits = filters.state.data.setdefault("history_limits", {})
        self.last_urls: dict[str, str] = {}

    async def handle(
        self,
        nick: str,
        target: str,
        text: str,
        send: Callable[[str, list[str]], Awaitable[None]],
        event: MessageEvent | None = None,
    ) -> None:
        prior_history = list(self.history[target])
        try:
            if self.triggers.enabled("reminders"):
                reminder_alerts = self.reminders.pop_due(clean_nick(nick), target)
                if reminder_alerts:
                    await send(target, reminder_alerts)

            if is_golem_control_command(text):
                if not self.triggers.enabled("golem"):
                    return
                reply = self.golem.handle(text)
                if reply:
                    if reply == ["* Context cleared *"]:
                        self.history[target].clear()
                        clear_channel_history(self.filters.state, target)
                    await send(target, reply)
                return

            if text.strip().lower().startswith("!clear"):
                if not self.triggers.enabled("clearhistory"):
                    return
                self.history[target].clear()
                clear_channel_history(self.filters.state, target)
                await send(target, ["* Context cleared *"])
                return

            history_reply = self.handle_history_command(target, text)
            if history_reply:
                await send(target, history_reply)
                return

            if is_reminder_command(text):
                if not self.triggers.enabled("reminders"):
                    return
                reminder_reply = self.reminders.handle(clean_nick(nick), target, text)
                if reminder_reply:
                    await send(target, reminder_reply)
                return

            if text.strip().lower() in {"!list", "!listen"}:
                running = self.running.list()
                await send(target, running or ["No commands running."])
                return

            if text.strip().lower() == "!drink":
                if not self.triggers.enabled("drink"):
                    return
                task = asyncio.create_task(self._run_bluesky(send, target))
                self.running.add(task, "drink args=[]", target)
                return

            if is_img2irc_command(text):
                if not self.triggers.enabled(img2irc_trigger_name(text)):
                    return
                task = asyncio.create_task(self._run_img2irc(send, target, text))
                self.running.add(task, img2irc_trigger_name(text), target)
                return

            if is_summary_command(text):
                if not self.summary_trigger_enabled(text):
                    return
                if self.summary_runner is None and self.llm_client is None:
                    await send(target, ["OpenRouter is not configured. Set OPENROUTER_API_KEY."])
                    return
                task = asyncio.create_task(self._run_summary(send, target, text))
                self.running.add(task, "summary", target)
                return

            reply = self.handle_sync(nick, text, target, event)
            if reply:
                await send(target, reply.lines)
                return

            generated_reply = self.generated_commands.handle(
                nick,
                target,
                text,
                self.triggers.enabled,
                event,
            )
            if generated_reply:
                await send(target, generated_reply)
                return

            llm = parse_llm_prompt(text, self.aliases.names())
            if llm and self.llm_triggers_enabled and self.triggers.enabled("gpt"):
                model_key, prompt = llm
                model = self.model_for_llm_key(model_key)
                if self.llm_client is None:
                    await send(target, ["OpenRouter is not configured. Set OPENROUTER_API_KEY."])
                    return
                prompt, options = parse_llm_options(prompt)
                prompt = self.with_history_context(
                    target,
                    prompt,
                    prior_history,
                    max_history=options.max_history,
                )
                task = asyncio.create_task(
                    self._run_llm(
                        send,
                        target,
                        prompt,
                        model,
                        prior_history,
                        temperature=options.temperature,
                        system=options.system,
                    )
                )
                self.running.add(task, model_key, target)
                return

            if (
                self.preview_urls_enabled
                and self.triggers.enabled("link_title")
                and not text.startswith("!")
            ):
                url = first_url(text)
                if url:
                    if is_youtube_url(url) and not self.triggers.enabled("youtube"):
                        return
                    task = asyncio.create_task(self._run_preview(send, target, url))
                    self.running.add(task, "preview", target)
        finally:
            url = first_url(text)
            if url:
                self.last_urls[target] = url
            if not text.startswith("!"):
                self.history[target].append((clean_nick(nick), text))
                record_history(self.filters.state, target, clean_nick(nick), text)

    async def handle_event(
        self,
        event: MessageEvent,
        send: Callable[[str, list[str]], Awaitable[None]],
    ) -> None:
        for reply in self.generated_commands.handle_event(event, self.triggers.enabled):
            await send(reply.target, reply.lines)

    def handle_sync(
        self,
        nick: str,
        text: str,
        generated_target: str = "_sync",
        event: MessageEvent | None = None,
    ) -> RoutedReply | None:
        stripped = text.strip()
        lowered = stripped.lower()
        if lowered == "!cancel":
            enabled = toggle_llm_tool_cancellation(self.filters.state)
            state = "ON" if enabled else "OFF"
            return RoutedReply([f"Tool cancellation flag is {state}"])
        tool_toggle_reply = handle_tool_toggle(stripped, self.filters.state)
        if tool_toggle_reply:
            return RoutedReply(tool_toggle_reply)
        trigger_reply = self.triggers.handle(stripped)
        if trigger_reply:
            return RoutedReply(trigger_reply)
        if is_reload_command(stripped):
            generated_reload = self.handle_generated_reload(stripped)
            if generated_reload:
                return RoutedReply(generated_reload)
            return RoutedReply(render_reload_command(stripped))
        if is_test_command(stripped):
            if not self.triggers.enabled("test"):
                return None
            return RoutedReply(self.test_renderer(stripped))
        if is_fortune_command(stripped):
            if not self.triggers.enabled("iching"):
                return None
            return RoutedReply(self.fortune_renderer(stripped))
        if lowered == "!kill all":
            ids = self.running.kill_all()
            killed = ", ".join(str(item) for item in ids)
            return RoutedReply([f"Killed all running commands: {killed}"])
        kill_match = re.match(r"^!kill\s+(\d+)$", lowered)
        if kill_match:
            task_id = int(kill_match.group(1))
            if self.running.kill(task_id):
                return RoutedReply([f"Killed run #{task_id}"])
            return RoutedReply([f"No such run #{task_id}"])
        if lowered == "ping":
            if not self.triggers.enabled("ping"):
                return None
            return RoutedReply(["p0ng!"])
        if is_blair_command(stripped):
            if not self.triggers.enabled("howsblair"):
                return None
            try:
                return RoutedReply(self.blair_renderer(stripped))
            except BlairCommandError as exc:
                return RoutedReply([str(exc)])
        if is_blair2_command(stripped):
            if not self.triggers.enabled("howsblair2"):
                return None
            try:
                return RoutedReply(self.blair2_renderer(stripped))
            except BlairCommandError as exc:
                return RoutedReply([str(exc)])
        if is_chkdomain_command(stripped):
            if not self.triggers.enabled("chkdomain"):
                return None
            return RoutedReply(self.chkdomain_renderer(stripped))
        if is_host_command(stripped):
            if not self.triggers.enabled("host"):
                return None
            return RoutedReply(self.host_renderer(stripped))
        if is_crt_command(stripped):
            if not self.triggers.enabled("crt"):
                return None
            return RoutedReply(self.crt_renderer(stripped, clean_nick(nick)))
        if is_chess_command(stripped):
            if not self.triggers.enabled("chess"):
                return None
            chess_reply = self.chess.handle(clean_nick(nick), stripped)
            if chess_reply:
                return RoutedReply(chess_reply)
        if is_horoscope_command(stripped):
            if not self.triggers.enabled("horoscope"):
                return None
            return RoutedReply(self.horoscope_renderer(stripped, clean_nick(nick)))
        if is_gay_command(stripped):
            if not self.triggers.enabled("gay"):
                return None
            try:
                return RoutedReply(self.gay_renderer(stripped))
            except GayCommandError as exc:
                return RoutedReply([str(exc)])
        if is_godsays_command(stripped):
            if not self.triggers.enabled("godsays"):
                return None
            return RoutedReply(self.godsays_renderer(stripped))
        if lowered == "!cmds":
            if not self.triggers.enabled("cmdlist"):
                return None
            return RoutedReply(
                render_command_table(
                    self.triggers.enabled,
                    self.generated_commands.command_entries(),
                )
            )
        if is_kv_command(stripped):
            if not self.triggers.enabled("kv"):
                return None
            kv_reply = self.kvstore.handle(stripped)
            if kv_reply:
                return RoutedReply(kv_reply)
        if is_eval_command(stripped):
            if not self.triggers.enabled("eval"):
                return None
            return RoutedReply(
                render_eval_command(
                    stripped,
                    generated_target,
                    clean_nick(nick),
                    getattr(event, "username", "") if event is not None else "",
                    getattr(event, "hostname", "") if event is not None else "",
                )
            )
        if is_phenoguessr_command(stripped):
            if not self.triggers.enabled("phenoguessr"):
                return None
            pheno_reply = self.phenoguessr.handle(
                clean_nick(nick),
                stripped,
                getattr(event, "username", "") if event is not None else "",
                getattr(event, "hostname", "") if event is not None else "",
            )
            if pheno_reply:
                return RoutedReply(pheno_reply)
        if is_trivia_command(stripped):
            if not self.triggers.enabled("trivia"):
                return None
            trivia_reply = self.trivia.handle(
                clean_nick(nick),
                generated_target,
                stripped,
                getattr(event, "username", "") if event is not None else "",
                getattr(event, "hostname", "") if event is not None else "",
            )
            if trivia_reply:
                return RoutedReply(trivia_reply)
            return None
        if (
            self.triggers.enabled("trivia")
            and self.trivia.active(generated_target)
            and not stripped.startswith(("!", "?"))
            and first_url(stripped) is None
            and parse_llm_prompt(stripped, self.aliases.names()) is None
        ):
            trivia_reply = self.trivia.handle(
                clean_nick(nick),
                generated_target,
                stripped,
                getattr(event, "username", "") if event is not None else "",
                getattr(event, "hostname", "") if event is not None else "",
            )
            if trivia_reply:
                return RoutedReply(trivia_reply)
            return None
        if is_poll_command(stripped):
            poll_trigger = "vote" if lowered.startswith("!vote") else "poll"
            if not self.triggers.enabled(poll_trigger):
                return None
            if re.fullmatch(r"[A-Za-z0-9]", stripped) and self.polls.active(generated_target) is None:
                return None
            poll_reply = self.polls.handle(clean_nick(nick), generated_target, stripped)
            if poll_reply:
                return RoutedReply(poll_reply)
        if is_palette99_command(stripped):
            if not self.triggers.enabled("palette99"):
                return None
            return RoutedReply(render_palette99())
        if lowered in {"!tools", "!tools enabled"}:
            if not self.triggers.enabled("tools"):
                return None
            return RoutedReply(render_tools_table(self.filters.state))
        if is_llm_prices_command(stripped):
            if not self.triggers.enabled("llm_prices"):
                return None
            try:
                return RoutedReply(self.llm_prices_renderer(stripped))
            except LLMPricesError as exc:
                return RoutedReply([str(exc)])
        if is_models_command(stripped):
            if not self.triggers.enabled("models"):
                return None
            try:
                return RoutedReply(self.models_renderer(stripped))
            except ModelsCommandError as exc:
                return RoutedReply([str(exc)])
        if is_radio_help_command(stripped):
            if not self.triggers.enabled("radio"):
                return None
            return RoutedReply(render_radio_help())
        radio_reply = self.radio.handle(stripped)
        if radio_reply:
            if not self.triggers.enabled("radio"):
                return None
            return RoutedReply(radio_reply)
        if lowered == "!hf":
            if not self.triggers.enabled("hf"):
                return None
            try:
                return RoutedReply(self.hf_renderer(stripped))
            except HuggingFaceCommandError as exc:
                return RoutedReply([str(exc)])
        if is_urban_command(stripped):
            if not self.triggers.enabled("urbandict"):
                return None
            try:
                return RoutedReply(self.urban_renderer(stripped))
            except UrbanDictCommandError as exc:
                return RoutedReply([str(exc)])
        if is_define_command(stripped):
            if not self.triggers.enabled("define"):
                return None
            try:
                return RoutedReply(self.define_renderer(stripped))
            except DefineCommandError as exc:
                return RoutedReply([str(exc)])
        if is_cp_command(stripped):
            if not self.triggers.enabled("cp"):
                return None
            try:
                return RoutedReply(self.cp_renderer(stripped))
            except CryptoPriceError as exc:
                return RoutedReply([str(exc)])
        if is_curl_command(stripped):
            trigger = "curl2" if lowered.startswith("!curl2 ") else "curl"
            if not self.triggers.enabled(trigger):
                return None
            try:
                return RoutedReply(self.curl_renderer(stripped))
            except CurlCommandError as exc:
                return RoutedReply([str(exc)])
        if is_ansi2irc_command(stripped):
            if not self.triggers.enabled("ansi2irc"):
                return None
            try:
                return RoutedReply(self.ansi2irc_renderer(stripped))
            except Ansi2IRCError as exc:
                return RoutedReply([str(exc)])
        if is_cat_command(stripped):
            if not self.triggers.enabled("cat"):
                return None
            return RoutedReply(self.cat_renderer(stripped))
        if is_mdcat_command(stripped):
            if not self.triggers.enabled("mdcat"):
                return None
            return RoutedReply(self.mdcat_renderer(stripped))
        if is_figlet_command(stripped):
            if not self.triggers.enabled("figlet"):
                return None
            return RoutedReply(self.figlet_renderer(stripped))
        if is_light_command(stripped):
            if not self.triggers.enabled("lepro"):
                return None
            return RoutedReply(self.light_renderer(stripped))
        if is_livebench_command(stripped):
            if not self.triggers.enabled("livebench"):
                return None
            return RoutedReply(self.livebench_renderer(stripped))
        if is_ytsearch_command(stripped):
            if not self.triggers.enabled("ytsearch"):
                return None
            try:
                return RoutedReply(self.ytsearch_renderer(stripped))
            except YTSearchError as exc:
                return RoutedReply([str(exc)])
        if is_invite_command(stripped):
            if not self.triggers.enabled("invite"):
                return None
            return RoutedReply(self.invite_renderer(stripped))
        if is_seen_command(stripped):
            if not self.triggers.enabled("seen"):
                return None
            return RoutedReply(
                render_seen_command(
                    stripped,
                    self.filters.state,
                    generated_target,
                    clean_nick(nick),
                )
            )
        if is_random_command(stripped):
            if not self.triggers.enabled("random"):
                return None
            return RoutedReply(self.random_renderer(stripped))
        if is_ligma_command(stripped):
            if not self.triggers.enabled("ligma"):
                return None
            try:
                return RoutedReply(self.ligma_renderer(stripped))
            except LigmaCommandError as exc:
                return RoutedReply([str(exc)])
        if is_nostr_command(stripped):
            if not self.triggers.enabled("nostr"):
                return None
            try:
                return RoutedReply(self.nostr_renderer(stripped))
            except NostrCommandError as exc:
                return RoutedReply([str(exc)])
        if is_twitter_command(stripped):
            if not self.triggers.enabled("twitter"):
                return None
            try:
                return RoutedReply(self.twitter_renderer(stripped))
            except TwitterCommandError as exc:
                return RoutedReply([str(exc)])
        if is_ufc_command(stripped):
            if not self.triggers.enabled("ufc"):
                return None
            try:
                return RoutedReply(self.ufc_renderer(stripped))
            except UFCCommandError as exc:
                return RoutedReply([str(exc)])
        if is_vocoder_command(stripped):
            if not self.triggers.enabled("vocoder"):
                return None
            try:
                return RoutedReply(self.vocoder_renderer(stripped))
            except VocoderCommandError as exc:
                return RoutedReply([str(exc)])
        if is_imdb_command(stripped):
            if not self.triggers.enabled("imdb"):
                return None
            try:
                return RoutedReply(self.imdb_renderer(stripped))
            except ImdbCommandError as exc:
                return RoutedReply([str(exc)])
        alias_reply = self.aliases.handle(stripped)
        if alias_reply:
            if not self.triggers.enabled("llm_alias"):
                return None
            return RoutedReply(alias_reply)
        if lowered.startswith("!stock "):
            if not self.triggers.enabled("stocks"):
                return None
            try:
                return RoutedReply(self.stock_renderer(stripped))
            except StockCommandError as exc:
                return RoutedReply([str(exc)])
        if lowered.startswith("!weather"):
            if not self.triggers.enabled("weather"):
                return None
            try:
                return RoutedReply(self.weather_renderers.weather(stripped))
            except WeatherCommandError as exc:
                return RoutedReply([str(exc)])
        if lowered.startswith("!forecast"):
            if not self.triggers.enabled("forecast"):
                return None
            try:
                return RoutedReply(self.weather_renderers.forecast(stripped))
            except WeatherCommandError as exc:
                return RoutedReply([str(exc)])
        if lowered.startswith("!vtrade"):
            if not self.triggers.enabled("vtrade"):
                return None
            return RoutedReply(self.vtrade.handle(clean_nick(nick), stripped))
        if is_zscore_command(stripped):
            if not self.triggers.enabled("zscore"):
                return None
            return RoutedReply(self.zscore_renderer(stripped))
        if is_echo_command(stripped):
            if not self.triggers.enabled("echo"):
                return None
            return RoutedReply(self.echo_renderer(stripped))
        if is_cowsay_command(stripped):
            if not self.triggers.enabled("cows"):
                return None
            return RoutedReply(self.cowsay_renderer(stripped))
        if is_todo_command(stripped):
            if not self.triggers.enabled("todo"):
                return None
            todo_reply = self.todos.handle(clean_nick(nick), stripped)
            if todo_reply:
                return RoutedReply(todo_reply)
        ascii_reply = self.ascii_art.handle(stripped)
        if ascii_reply:
            if not self.triggers.enabled("ascii"):
                return None
            return RoutedReply(ascii_reply)
        if lowered.startswith("!ai "):
            return None
        if lowered.startswith("!summary"):
            return None
        filter_trigger = filter_trigger_name(stripped)
        if filter_trigger and not self.triggers.enabled(filter_trigger):
            return None
        filter_reply = self.filters.handle(stripped)
        if filter_reply:
            return RoutedReply(filter_reply)
        generated_reply = self.generated_commands.handle(
            nick,
            generated_target,
            stripped,
            self.triggers.enabled,
            event,
        )
        if generated_reply:
            return RoutedReply(generated_reply)
        return None

    def handle_generated_reload(self, text: str) -> list[str] | None:
        parts = text.strip().split(maxsplit=1)
        if len(parts) == 1:
            return None
        module = parts[1].strip()
        if module == "generated_commands":
            return self.generated_commands.reload()
        if module.startswith("generated_commands."):
            return self.generated_commands.reload(module.rsplit(".", 1)[1])
        root = self.filters.state.data.setdefault("generated_commands", {})
        if module in root:
            return self.generated_commands.reload(module)
        return None

    def run_llm_tool_command(
        self,
        context: LLMToolContext,
        cmd_name: str,
        args: list[str],
    ) -> list[str] | None:
        for candidate in run_tool_command_texts(cmd_name, args):
            reply = self.handle_sync(BOT_NICK, candidate, context.target)
            if reply is not None:
                return reply.lines
        return None

    def handle_history_command(self, target: str, text: str) -> list[str] | None:
        stripped = text.strip()
        if not stripped.lower().startswith("!history"):
            return None
        parts = stripped.split()
        if len(parts) == 1:
            return [f"max_history is set to: {self.max_history_for(target)}"]
        if len(parts) != 2 or not parts[1].isdigit():
            return ["Usage: !history [max_lines]"]
        limit = max(0, min(int(parts[1]), 2000))
        self.history_limits[target] = limit
        self.filters.state.save()
        return [f"set max_history to: {limit}"]

    def max_history_for(self, target: str) -> int:
        return int(self.history_limits.get(target, 5))

    def with_history_context(
        self,
        target: str,
        prompt: str,
        prior_history: list[tuple[str, str]],
        max_history: int | None = None,
    ) -> str:
        if max_history is None:
            max_history = self.max_history_for(target)
        if max_history <= 0 or not prior_history:
            return prompt
        lines = [f"{nick}: {message}" for nick, message in prior_history[-max_history:]]
        return "Recent IRC context:\n" + "\n".join(lines) + "\n\nUser prompt:\n" + prompt

    def summary_trigger_enabled(self, text: str) -> bool:
        lowered = text.strip().lower()
        if lowered.startswith("!wsummary") or lowered.startswith("! wsummary"):
            return self.triggers.enabled("wsummary")
        return self.triggers.enabled("ytsummary")

    def model_for_llm_key(self, model_key: str) -> str:
        if model_key == "gpt":
            return normalize_model_id(self.aliases.default_model())
        alias_model = self.aliases.model_for(model_key)
        if alias_model is not None:
            return alias_model
        if model_key == "grok":
            return self.grok_model
        return normalize_model_id(model_key)

    async def _run_llm(
        self,
        send: Callable[[str, list[str]], Awaitable[None]],
        target: str,
        prompt: str,
        model: str,
        prior_history: list[tuple[str, str]] | None = None,
        temperature: float | None = None,
        system: str = "",
    ) -> None:
        assert self.llm_client is not None
        try:
            tools = self.llm_tools.bind(
                LLMToolContext(
                    target=target,
                    history=tuple(prior_history or ()),
                    state=self.filters.state,
                )
            )
            result = await asyncio.to_thread(
                self._chat_with_compat,
                prompt,
                model,
                tools,
                temperature,
                system,
            )
            lines = list(result.tool_traces) + result.lines + [stats_line(result)]
            if result.lines:
                record_history(
                    self.filters.state,
                    target,
                    BOT_NICK,
                    "\n".join(result.lines),
                    role="assistant",
                    model=result.model,
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            lines = [f"LLM error: {exc}"]
        await send(target, self._split(lines))

    def _chat_with_compat(
        self,
        prompt: str,
        model: str,
        tools,
        temperature: float | None,
        system: str,
    ):
        assert self.llm_client is not None
        kwargs = {"tools": tools}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if system:
            kwargs["extra_system"] = system
        if callable_accepts_keyword(self.llm_client.chat, "cancel_checker"):
            kwargs["cancel_checker"] = self.llm_tool_cancellation_enabled
        try:
            return self.llm_client.chat(prompt, model, **kwargs)
        except TypeError as exc:
            if "unexpected keyword" not in str(exc) and "positional" not in str(exc):
                raise
        try:
            return self.llm_client.chat(prompt, model, tools=tools)
        except TypeError as exc:
            if "unexpected keyword" not in str(exc) and "positional" not in str(exc):
                raise
        return self.llm_client.chat(prompt, model)

    def llm_tool_cancellation_enabled(self) -> bool:
        return bool(self.filters.state.data.get(LLM_TOOL_CANCELLATION_KEY))

    async def _run_bluesky(
        self,
        send: Callable[[str, list[str]], Awaitable[None]],
        target: str,
    ) -> None:
        try:
            if self.bluesky_runner is not None:
                await self.bluesky_runner(send, target)
            else:
                watcher = BlueskyFeedWatcher(
                    self.filters,
                    self.filters.state,
                    poll_seconds=self.bluesky_poll_seconds,
                    search_limit=self.bluesky_search_limit,
                )
                await watcher.run(send, target)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await send(target, [f"Bluesky error: {exc}"])

    async def _run_preview(
        self,
        send: Callable[[str, list[str]], Awaitable[None]],
        target: str,
        url: str,
    ) -> None:
        try:
            line = await asyncio.to_thread(preview_title, url)
        except asyncio.CancelledError:
            raise
        except Exception:
            return
        await send(target, [line])

    async def _run_img2irc(
        self,
        send: Callable[[str, list[str]], Awaitable[None]],
        target: str,
        text: str,
    ) -> None:
        try:
            lines = await asyncio.to_thread(self.image_renderer, text)
        except asyncio.CancelledError:
            raise
        except Img2IRCError as exc:
            lines = [f"img2irc error: {exc}"]
        except Exception as exc:
            lines = [f"img2irc error: {exc}"]
        await send(target, self._split(lines))

    async def _run_summary(
        self,
        send: Callable[[str, list[str]], Awaitable[None]],
        target: str,
        text: str,
    ) -> None:
        try:
            if self.summary_runner is not None:
                lines = await asyncio.to_thread(
                    self.summary_runner, text, self.last_urls.get(target)
                )
            else:
                assert self.llm_client is not None
                lines = await asyncio.to_thread(
                    run_summary_command,
                    text,
                    self.last_urls.get(target),
                    self.llm_client,
                    self.grok_model,
                )
        except asyncio.CancelledError:
            raise
        except SummaryError as exc:
            lines = [f"summary error: {exc}"]
        except Exception as exc:
            lines = [f"summary error: {exc}"]
        await send(target, self._split(lines))

    def _split(self, lines: list[str]) -> list[str]:
        out: list[str] = []
        for line in lines:
            out.extend(split_irc_lines(line, self.max_irc_line))
        return out


def parse_llm_prompt(text: str, aliases: set[str] | None = None) -> tuple[str, str] | None:
    stripped = text.strip()
    lowered = stripped.lower()
    aliases = set(DEFAULT_ALIASES) if aliases is None else aliases
    valid_names = {"gpt", "grok", *aliases}
    if lowered.startswith("!ai "):
        return "gpt", stripped[4:].strip()
    if lowered.startswith("!summary"):
        rest = stripped[len("!summary") :].strip()
        if not rest:
            return "gpt", "Summarize the recent channel context."
        return "gpt", f"Summarize this concisely for IRC: {rest}"
    for trigger, model_key in LLM_TRIGGERS:
        if lowered.startswith(trigger):
            prompt = stripped[len(trigger) :].strip(" ,:")
            if prompt:
                return model_key, prompt
    match = re.match(r"^@@?(\S+)\s+(.+)$", stripped, flags=re.IGNORECASE)
    if match:
        raw_name = match.group(1).strip(",:")
        name = raw_name.lower()
        if name in valid_names:
            return name, match.group(2).strip()
        if "/" in raw_name:
            return raw_name, match.group(2).strip()
    match = re.match(r"^(gpt|grok)\s+(.+)$", stripped, flags=re.IGNORECASE)
    if match:
        return match.group(1).lower(), match.group(2).strip()
    match = re.match(r"^([A-Za-z][\w.-]*)([,:])\s+(.+)$", stripped)
    if match:
        name = match.group(1).lower()
        if name in valid_names:
            return name, match.group(3).strip()
    return None


def parse_llm_options(prompt: str) -> tuple[str, LLMOptions]:
    max_history: int | None = None
    temperature: float | None = None
    system = ""
    pos = _skip_option_separators(prompt, 0)
    consumed = False
    while pos < len(prompt):
        start = pos
        match = re.match(
            r"(maxh|max_history|temperature|system)=",
            prompt[pos:],
            flags=re.IGNORECASE,
        )
        if not match:
            break
        key = match.group(1).lower()
        value_start = pos + len(match.group(0))
        parsed = _parse_option_value(prompt, value_start, quoted=key == "system")
        if parsed is None:
            break
        raw_value, value_end = parsed
        if key in {"maxh", "max_history"}:
            if not re.fullmatch(r"[+-]?\d+", raw_value):
                break
            max_history = max(0, min(int(raw_value), 2000))
        elif key == "temperature":
            if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", raw_value):
                break
            temperature = float(raw_value)
        else:
            system = raw_value
        consumed = True
        pos = _skip_option_separators(prompt, value_end)
        if pos == start:
            break
    if not consumed:
        return prompt.strip(), LLMOptions()
    return prompt[pos:].strip(), LLMOptions(
        max_history=max_history,
        temperature=temperature,
        system=system,
    )


def _skip_option_separators(text: str, pos: int) -> int:
    while pos < len(text) and (text[pos].isspace() or text[pos] == ","):
        pos += 1
    return pos


def _parse_option_value(
    text: str,
    value_start: int,
    quoted: bool = False,
) -> tuple[str, int] | None:
    if value_start >= len(text):
        return None
    if quoted and text[value_start] in {"'", '"'}:
        quote = text[value_start]
        pos = value_start + 1
        value: list[str] = []
        escaped = False
        while pos < len(text):
            char = text[pos]
            if escaped:
                value.append(char)
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                return "".join(value), pos + 1
            else:
                value.append(char)
            pos += 1
        return None
    pos = value_start
    while pos < len(text) and not text[pos].isspace() and text[pos] != ",":
        pos += 1
    if pos == value_start:
        return None
    return text[value_start:pos], pos


def run_tool_command_texts(cmd_name: str, args: list[str]) -> list[str]:
    name = cmd_name.strip().lower()
    arg_text = " ".join(str(arg) for arg in args).strip()
    if name == "ligma":
        if "ligma.pro/" in arg_text:
            return [arg_text]
        return [f"https://ligma.pro/@r000t/{arg_text}".strip()]

    def with_args(prefix: str) -> str:
        if prefix.endswith(":"):
            return f"{prefix}{arg_text}".strip()
        return f"{prefix} {arg_text}".strip()

    aliases = {
        "ansi2irc": ["!ansi2irc"],
        "ansi2irc2": ["!ansi2irc"],
        "irc2ansi": ["!irc2ansi"],
        "iching": ["!fortune"],
        "fortune": ["!fortune"],
        "horoscope": [".horoscope"],
        "zscore": ["!zscore", "!z"],
        "define": ["!define"],
        "urban": ["!urban"],
        "urbandict": ["!urban"],
        "host": ["!host"],
        "crt": ["!crt"],
        "cp": ["tcl cp"],
        "livebench": ["!livebench"],
        "nostr": ["nostr:"],
        "pheno": ["!pheno"],
        "phenoguessr": ["!pheno"],
        "twitter": ["!twitter"],
        "trivia": ["!trivia"],
        "ufc": ["!ufc"],
        "vocoder": ["!vocoder"],
        "teste": ["!teste"],
        "weather": ["!weather"],
        "forecast": ["!forecast"],
        "stock": ["!stock"],
        "stocks": ["!stock"],
        "models": ["!models"],
        "llm_prices": ["$llm"],
        "img2irc": ["!img2irc"],
        "imghax": ["!hax"],
        "invite": ["!invite"],
        "random": [".random"],
        "mdcat": ["!mdcat"],
        "cat": ["!cat"],
        "curl": ["!curl"],
        "curl2": ["!curl2"],
        "gay": ["!gay"],
        "light": ["!light"],
        "lepro": ["!light"],
        "cows": ["!cowsay"],
        "echo": ["!echo"],
        "todo": ["!todo"],
    }
    prefixes = aliases.get(name, [f"!{name}", name])
    candidates = [with_args(prefix) for prefix in prefixes]
    for fallback in (with_args(f"!{name}"), with_args(name)):
        if fallback not in candidates:
            candidates.append(fallback)
    return candidates


def filter_trigger_name(text: str) -> str | None:
    parts = text.strip().split(maxsplit=1)
    if not parts:
        return None
    return {
        "!add": "bwatchadd",
        "!blist": "bwatchlist",
        "!del": "bwatchdel",
    }.get(parts[0].lower())
