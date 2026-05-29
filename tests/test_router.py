from __future__ import annotations

import asyncio
import random
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone

from pyylmao.ascii_art import AsciiArtStore
from pyylmao.eval_command import reset_eval_builtins_for_tests
from pyylmao.filters import FilterStore
from pyylmao.golem import GolemControlStore
from pyylmao.generated_commands import MessageEvent
from pyylmao.history_store import history_items, record_history
from pyylmao.llm import LLMResult
from pyylmao.llm_tools import LLMToolContext
from pyylmao.phenoguessr import Location, PhenoguessrStore, PhenotypeEntry, StaticLocationResolver
from pyylmao.router import LLMOptions, Router, parse_llm_options, parse_llm_prompt
from pyylmao.reminders import ReminderStore
from pyylmao.state import JsonState
from pyylmao.trivia import TriviaQuestion, TriviaStore
from pyylmao.vtrade import StaticPriceProvider, VTrade
from pyylmao.weather import WeatherRenderers


class RouterTests(unittest.TestCase):
    def make_router(
        self,
        test_renderer=None,
        fortune_renderer=None,
        blair_renderer=None,
        blair2_renderer=None,
        gay_renderer=None,
        godsays_renderer=None,
        urban_renderer=None,
        define_renderer=None,
        cp_renderer=None,
        curl_renderer=None,
        cat_renderer=None,
        mdcat_renderer=None,
        figlet_renderer=None,
        light_renderer=None,
        livebench_renderer=None,
        ligma_renderer=None,
        nostr_renderer=None,
        twitter_renderer=None,
        ufc_renderer=None,
        imdb_renderer=None,
        vocoder_renderer=None,
        llm_prices_renderer=None,
        models_renderer=None,
        chkdomain_renderer=None,
        host_renderer=None,
        crt_renderer=None,
        horoscope_renderer=None,
        ytsearch_renderer=None,
        invite_renderer=None,
        random_renderer=None,
        raw_irc_sender=None,
        golem=None,
        kvstore=None,
        trivia=None,
        trivia_questions=None,
        phenoguessr=None,
        phenoguessr_entries=None,
        phenoguessr_locations=None,
        aliases=None,
        ansi2irc_renderer=None,
    ) -> Router:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = JsonState(Path(tmp.name) / "state.json")
        return Router(
            vtrade=VTrade(
                state,
                prices=StaticPriceProvider({"TSLA": "250"}),
                now=lambda: 1000.0,
                rng=random.Random(1),
            ),
            filters=FilterStore(state),
            llm_client=None,
            default_model="openai/gpt-oss-120b",
            grok_model="x-ai/grok-4.1-fast",
            ascii_art=AsciiArtStore.default(),
            blair_renderer=blair_renderer,
            blair2_renderer=blair2_renderer,
            test_renderer=test_renderer,
            fortune_renderer=fortune_renderer,
            gay_renderer=gay_renderer,
            godsays_renderer=godsays_renderer,
            urban_renderer=urban_renderer,
            define_renderer=define_renderer,
            cp_renderer=cp_renderer,
            curl_renderer=curl_renderer,
            cat_renderer=cat_renderer,
            mdcat_renderer=mdcat_renderer,
            figlet_renderer=figlet_renderer,
            light_renderer=light_renderer,
            livebench_renderer=livebench_renderer,
            ligma_renderer=ligma_renderer,
            nostr_renderer=nostr_renderer,
            twitter_renderer=twitter_renderer,
            ufc_renderer=ufc_renderer,
            imdb_renderer=imdb_renderer,
            vocoder_renderer=vocoder_renderer,
            llm_prices_renderer=llm_prices_renderer,
            models_renderer=models_renderer,
            chkdomain_renderer=chkdomain_renderer,
            host_renderer=host_renderer,
            crt_renderer=crt_renderer,
            horoscope_renderer=horoscope_renderer,
            ytsearch_renderer=ytsearch_renderer,
            invite_renderer=invite_renderer,
            random_renderer=random_renderer,
            raw_irc_sender=raw_irc_sender,
            golem=golem,
            kvstore=kvstore,
            trivia=trivia or (
                TriviaStore(state, questions=trivia_questions, rng=random.Random(1))
                if trivia_questions is not None
                else None
            ),
            phenoguessr=phenoguessr or (
                PhenoguessrStore(
                    state,
                    entries=phenoguessr_entries,
                    resolver=StaticLocationResolver(phenoguessr_locations or {}),
                    image_renderer=lambda command: [],
                    rng=random.Random(1),
                    now=lambda: 1779147183.162254,
                )
                if phenoguessr_entries is not None
                else None
            ),
            aliases=aliases,
            ansi2irc_renderer=ansi2irc_renderer,
        )

    def test_parse_llm_triggers_seen_in_logs(self) -> None:
        self.assertEqual(parse_llm_prompt("grok, when does memory bottleneck"), ("grok", "when does memory bottleneck"))
        self.assertEqual(parse_llm_prompt("@grok is iran imminent"), ("grok", "is iran imminent"))
        self.assertEqual(parse_llm_prompt("@@grok search for real sources"), ("grok", "search for real sources"))
        self.assertEqual(parse_llm_prompt("gpt, how many people"), ("gpt", "how many people"))
        self.assertEqual(parse_llm_prompt("hy, hi"), ("hy", "hi"))
        self.assertEqual(parse_llm_prompt("@@hy generate an artifact"), ("hy", "generate an artifact"))
        self.assertEqual(parse_llm_prompt("hy2, write a poem"), ("hy2", "write a poem"))
        self.assertEqual(parse_llm_prompt("luna, sup"), ("luna", "sup"))
        self.assertEqual(parse_llm_prompt("nemo9, maxh=1 hello"), ("nemo9", "maxh=1 hello"))
        self.assertEqual(parse_llm_prompt("mm, how much does steel cost"), ("mm", "how much does steel cost"))
        self.assertEqual(parse_llm_prompt("@@q move the date to the end"), ("q", "move the date to the end"))
        self.assertEqual(parse_llm_prompt("@@hunter create a 3d simulator"), ("hunter", "create a 3d simulator"))
        self.assertEqual(parse_llm_prompt("!ai hello"), ("gpt", "hello"))
        self.assertEqual(parse_llm_prompt("grok maxh=1 hello"), ("grok", "maxh=1 hello"))

    def test_parse_llm_triggers_accept_alias_names(self) -> None:
        aliases = {"d", "glm", "hy2", "moonshotai/kimi-k2.5"}
        self.assertEqual(parse_llm_prompt("@d hi", aliases), ("d", "hi"))
        self.assertEqual(parse_llm_prompt("@@glm create", aliases), ("glm", "create"))
        self.assertEqual(parse_llm_prompt("hy2, hi", aliases), ("hy2", "hi"))
        self.assertEqual(
            parse_llm_prompt("@@moonshotai/kimi-k2.5 hi", aliases),
            ("moonshotai/kimi-k2.5", "hi"),
        )
        self.assertEqual(
            parse_llm_prompt("@@OpenRouter/X-AI/Grok-4.3 hi", aliases),
            ("OpenRouter/X-AI/Grok-4.3", "hi"),
        )
        self.assertIsNone(parse_llm_prompt("spoke: hi", aliases))

    def test_parse_llm_options_seen_in_logs(self) -> None:
        self.assertEqual(parse_llm_options("maxh=1 hello"), ("hello", LLMOptions(max_history=1)))
        self.assertEqual(parse_llm_options("max_history=2 hello"), ("hello", LLMOptions(max_history=2)))
        self.assertEqual(
            parse_llm_options("maxh=1 temperature=2 tell me a joke"),
            ("tell me a joke", LLMOptions(max_history=1, temperature=2.0)),
        )
        self.assertEqual(
            parse_llm_options('maxh=1 system="You are a 1337 security researcher" hello'),
            ("hello", LLMOptions(max_history=1, system="You are a 1337 security researcher")),
        )
        self.assertEqual(
            parse_llm_options('system="" whats the sign'),
            ("whats the sign", LLMOptions(system="")),
        )
        self.assertEqual(
            parse_llm_options("maxh=1translate hello"),
            ("maxh=1translate hello", LLMOptions()),
        )
        self.assertEqual(
            parse_llm_options("maxh=2500 hello"),
            ("hello", LLMOptions(max_history=2000)),
        )

    def test_public_eval_debug_command_matches_generated_regex(self) -> None:
        reset_eval_builtins_for_tests()
        router = self.make_router()

        self.assertEqual(router.handle_sync("pizza2", 'eval "hello"', "#bowlcut").lines, ["hello"])
        self.assertEqual(
            router.handle_sync(
                "pizza2",
                "grok doesn't like writing commands that only match at the beginning of a line eval 1+2+3",
                "#bowlcut",
            ).lines,
            ["6"],
        )
        self.assertEqual(
            router.handle_sync("pizza2", "yeah no statements inside eval sadly", "#bowlcut").lines,
            ["Eval error: name 'sadly' is not defined"],
        )
        self.assertEqual(router.handle_sync("alice", "!disable eval").lines, ["Trigger eval is now disabled"])
        self.assertIsNone(router.handle_sync("pizza2", "eval 1+1", "#bowlcut"))

    def test_alias_command_routes_and_is_trigger_gated(self) -> None:
        router = self.make_router()
        self.assertEqual(
            router.handle_sync("alice", "!alias set glm openrouter/z-ai/glm-4.7").lines,
            ["Alias 'glm' set to 'openrouter/z-ai/glm-4.7'."],
        )
        self.assertEqual(
            router.handle_sync("alice", "!alias get glm").lines,
            ["'glm' -> 'openrouter/z-ai/glm-4.7'"],
        )
        self.assertEqual(
            router.handle_sync("alice", "!disable llm_alias").lines,
            ["Trigger llm_alias is now disabled"],
        )
        self.assertIsNone(router.handle_sync("alice", "!alias get glm"))

    def test_cp_routes_crypto_price_table_and_is_trigger_gated(self) -> None:
        calls = []
        router = self.make_router(cp_renderer=lambda text: calls.append(text) or ["cp table"])

        self.assertEqual(router.handle_sync("alice", "tcl cp btc eth", "#c").lines, ["cp table"])
        self.assertEqual(calls, ["tcl cp btc eth"])
        self.assertEqual(
            router.run_llm_tool_command(
                LLMToolContext("#c", (), router.filters.state),
                "cp",
                ["btc", "eth"],
            ),
            ["cp table"],
        )
        self.assertEqual(calls[-1], "tcl cp btc eth")
        self.assertEqual(router.handle_sync("alice", "!disable cp").lines, ["Trigger cp is now disabled"])
        self.assertIsNone(router.handle_sync("alice", "tcl cp btc", "#c"))

    def test_ytsearch_is_reconstructed_but_disabled_by_default(self) -> None:
        calls = []
        router = self.make_router(ytsearch_renderer=lambda text: calls.append(text) or ["yt result"])

        self.assertIsNone(router.handle_sync("alice", "!yt im not okay", "#c"))
        self.assertEqual(
            router.handle_sync("alice", "!enable ytsearch", "#c").lines,
            ["Trigger ytsearch is now enabled"],
        )
        self.assertEqual(router.handle_sync("alice", "!yt im not okay", "#c").lines, ["yt result"])
        self.assertEqual(calls, ["!yt im not okay"])

    def test_invite_is_reconstructed_but_disabled_by_default(self) -> None:
        sent: list[list[str]] = []
        router = self.make_router(raw_irc_sender=lambda commands: sent.append(commands) or "")

        self.assertIsNone(router.handle_sync("alice", "!invite malcom #bowlcut", "#c"))
        self.assertEqual(
            router.handle_sync("alice", "!enable invite", "#c").lines,
            ["Trigger invite is now enabled"],
        )
        self.assertEqual(
            router.handle_sync("alice", "!invite malcom #bowlcut", "#c").lines,
            ["Invited malcom to #bowlcut"],
        )
        self.assertEqual(sent, [["INVITE malcom :#bowlcut"]])

    def test_random_reconstructed_command_is_trigger_gated(self) -> None:
        router = self.make_router(random_renderer=lambda text: ["Random number between 1 and 3: 2"])

        self.assertEqual(
            router.handle_sync("alice", ".random 1 3", "#not-gay").lines,
            ["Random number between 1 and 3: 2"],
        )
        self.assertEqual(router.handle_sync("alice", "!disable random").lines, ["Trigger random is now disabled"])
        self.assertIsNone(router.handle_sync("alice", ".random 1 3", "#not-gay"))

    def test_seen_uses_channel_history_and_command_tool_context(self) -> None:
        router = self.make_router()
        record_history(router.filters.state, "#c", "alice", "hello there", ts=1766479443)

        self.assertEqual(
            router.handle_sync("bob", "!seen alice", "#c").lines,
            ["alice was last seen pon 2025-12-23 08:44:03 UTC saying: hello there"],
        )
        self.assertEqual(
            router.run_llm_tool_command(
                LLMToolContext("#c", (), router.filters.state),
                "seen",
                ["alice"],
            ),
            ["alice was last seen pon 2025-12-23 08:44:03 UTC saying: hello there"],
        )
        self.assertEqual(router.handle_sync("alice", "!disable seen").lines, ["Trigger seen is now disabled"])
        self.assertIsNone(router.handle_sync("bob", "!seen alice", "#c"))

    def test_generated_commands_route_and_reload_from_state(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = JsonState(Path(tmp.name) / "state.json")
        path = Path(tmp.name) / "hello.py"
        path.write_text(
            "def entrypoint(args, channel, nickname, username, hostname):\n"
            "    print(f'{nickname}: {args[0]}')\n",
            encoding="utf-8",
        )
        state.data["generated_commands"] = {
            "hello": {"path": str(path), "pattern": r"^!hello (.+)$"}
        }
        router = Router(
            vtrade=VTrade(state, prices=StaticPriceProvider({"TSLA": "250"})),
            filters=FilterStore(state),
            llm_client=None,
            default_model="openai/gpt-oss-120b",
            grok_model="x-ai/grok-4.1-fast",
        )

        self.assertEqual(router.handle_sync("~Alice", "!hello world").lines, ["Alice: world"])
        self.assertEqual(
            router.handle_sync("alice", "!reload hello").lines,
            ["reloaded:", "- generated_commands.hello"],
        )
        self.assertEqual(
            router.handle_sync("alice", "!disable hello").lines,
            ["Trigger hello is now disabled"],
        )
        self.assertIsNone(router.handle_sync("alice", "!hello world"))
        table = "\n".join(router.handle_sync("alice", "!cmds").lines)
        self.assertIn("|    hello     |  False  |", table)
        self.assertIn(r"^!hello (.+)$", table)

    def test_unknown_generated_trigger_must_exist_before_enable(self) -> None:
        router = self.make_router()
        self.assertEqual(
            router.handle_sync("alice", "!enable doesnotexist").lines,
            ["Trigger doesnotexist does not exist"],
        )

    def test_phenoguessr_routes_logged_generated_command_surface(self) -> None:
        entry = PhenotypeEntry(
            "sample",
            "Sample Label",
            0.0,
            0.0,
            accepted=("target",),
        )
        router = self.make_router(
            phenoguessr_entries=[entry],
            phenoguessr_locations={
                "target": Location("Target", 0.0, 1.0),
                "far": Location("Far", 0.0, 40.0),
            },
        )

        self.assertEqual(
            router.handle_sync("alice", "!enable phenoguessr").lines,
            ["Trigger phenoguessr is now enabled"],
        )
        self.assertEqual(
            router.handle_sync("alice", "!pheno", "#not-gay").lines,
            ["New phenotype guesser started! Guess the location with !pheno <location>"],
        )
        wrong = router.handle_sync("~Alice", "!pheno far", "#not-gay").lines
        self.assertEqual(wrong, ["Alice guessed far. Incorrect! 4447.8 km (2763.73 mi) away."])
        self.assertEqual(
            router.handle_sync("@Alice", "!pheno target", "#not-gay").lines,
            ["Alice guessed target! BULLSEYE! Score: 5000 (111.19 km away). It was Sample Label! They win!"],
        )
        root = router.filters.state.data["kvstore"]["commands"]["phenoguessr"]
        self.assertEqual(root["stats"]["Alice"]["correct_guesses"], 1)
        self.assertEqual(root["stats"]["Alice"]["incorrect_guesses"], 1)

        self.assertEqual(
            router.handle_sync("alice", "!disable phenoguessr").lines,
            ["Trigger phenoguessr is now disabled"],
        )
        self.assertIsNone(router.handle_sync("alice", "!pheno", "#not-gay"))

    def test_model_for_llm_key_uses_aliases_and_default_model_alias(self) -> None:
        router = self.make_router()
        self.assertEqual(router.model_for_llm_key("hy"), "tencent/hy3-preview")
        self.assertEqual(router.model_for_llm_key("q"), "qwen/qwen3.6-plus:free")
        self.assertEqual(router.model_for_llm_key("nemo9"), "nvidia/nemotron-nano-9b-v2")

        router.aliases.set("hy2", "openrouter/tencent/hy3-preview")
        self.assertEqual(router.model_for_llm_key("hy2"), "tencent/hy3-preview")

        router.aliases.set("grok", "openrouter/x-ai/grok-4.3")
        self.assertEqual(router.model_for_llm_key("grok"), "x-ai/grok-4.3")

        router.aliases.handle("!alias set-default hy2")
        self.assertEqual(router.model_for_llm_key("gpt"), "tencent/hy3-preview")
        self.assertEqual(router.model_for_llm_key("openrouter/x-ai/grok-4.3"), "x-ai/grok-4.3")

    def test_llm_run_tool_can_dispatch_reconstructed_command_names(self) -> None:
        router = self.make_router(
            define_renderer=lambda text: [f"define called: {text}"],
            horoscope_renderer=lambda text, nick: [f"horoscope called: {text} / {nick}"],
        )

        self.assertEqual(
            router.llm_tools.execute(
                LLMToolContext("#c", (), router.filters.state),
                "run",
                {"cmd_name": "define", "args": "['gay']"},
            ),
            "define called: !define gay",
        )
        self.assertEqual(
            router.llm_tools.execute(
                LLMToolContext("#c", (), router.filters.state),
                "run",
                {"cmd_name": "horoscope", "args": "['leo']"},
            ),
            "horoscope called: .horoscope leo / pyylmao",
        )

    def test_sync_routes_vtrade_and_filters(self) -> None:
        router = self.make_router()
        self.assertEqual(
            router.handle_sync("alice", "!vtrade claim alice").lines,
            ["alice claimed. Starting balance: $1,000.00 USD."],
        )
        self.assertEqual(router.handle_sync("alice", "!add test").lines, ["1) test"])
        self.assertEqual(router.handle_sync("alice", "!blist").lines, ["1) test"])
        self.assertEqual(router.handle_sync("alice", "!del 1").lines, ["No tracked filters."])

    def test_poll_and_vote_match_logged_generated_command_surface(self) -> None:
        router = self.make_router()
        created = router.handle_sync("alice", "!poll Favorite? A. Pizza B. Tacos").lines
        self.assertEqual(created[:3], [
            "🗳️ New Poll: Favorite? started by alice:",
            "A: Pizza",
            "B: Tacos",
        ])
        self.assertIn("Reply with just A, B to vote", created[-1])

        vote = router.handle_sync("bob", "B").lines
        self.assertEqual(vote[0], "✅ bob voted B! 🗳️")
        self.assertIn("B: Tacos 👑 (1)", vote)
        self.assertIn("Total votes: 1", vote)

        shown = router.handle_sync("alice", "?poll").lines
        self.assertEqual(shown[0], "📊 Current Poll:")
        self.assertIn("Favorite?", shown)
        self.assertIn("B: Tacos 👑 (1)", shown)

        self.assertEqual(router.handle_sync("alice", "!poll stop").lines, ["🛑 Poll stopped by alice!"])
        self.assertIsNone(router.handle_sync("bob", "A"))

    def test_poll_accepts_logged_numeric_flexible_form_and_vote_command(self) -> None:
        router = self.make_router()
        created = router.handle_sync("alice", "!poll does this work? yes/no/kind of").lines
        self.assertEqual(created[:4], [
            "🗳️ New Poll: does this work? started by alice:",
            "1: yes",
            "2: no",
            "3: kind of",
        ])
        vote = router.handle_sync("bob", "!vote 3").lines
        self.assertEqual(vote[0], "✅ bob voted 3! 🗳️")
        self.assertIn("3: kind of 👑 (1)", vote)

        invalid = router.handle_sync("carol", "!vote pizza").lines
        self.assertEqual(invalid, ["carol: Invalid option 'PIZZA'. Valid options: 1, 2, 3"])

        self.assertEqual(
            router.handle_sync("alice", "!disable poll").lines,
            ["Trigger poll is now disabled"],
        )
        self.assertIsNone(router.handle_sync("alice", "!poll Another? A. One B. Two"))

    def test_trivia_matches_logged_generated_command_surface(self) -> None:
        questions = [
            TriviaQuestion(
                "In which US state is the active Mount Rainier volcano located?",
                "Washington",
                "history",
                "medium",
            ),
            TriviaQuestion(
                "The Punic Wars were a series of three wars fought between these two powers.",
                "Rome and Carthage",
                "history",
                "medium",
            ),
        ]
        router = self.make_router(trivia_questions=questions)

        categories = router.handle_sync("alice", "!trivia categories", "#not-gay").lines
        self.assertEqual(categories[0], "Available categories:")
        self.assertIn("• History", categories)
        self.assertEqual(categories[-1], "Use !trivia category any or names for random/specific.")

        self.assertEqual(
            router.handle_sync("alice", "!trivia category history", "#not-gay").lines,
            ["Categories set to: History."],
        )
        self.assertEqual(
            router.handle_sync("alice", "!trivia threshold 0.2", "#not-gay").lines,
            ["Threshold set to 0.20."],
        )
        question = router.handle_sync("alice", "!trivia", "#not-gay").lines
        self.assertEqual(
            question,
            [
                "In which US state is the active Mount Rainier volcano located? "
                "\x0314(medium - History)\x03"
            ],
        )

        self.assertIsNone(router.handle_sync("bob", "oregon", "#not-gay"))
        self.assertIsNone(router.handle_sync("bob", "gpt, whats a radian", "#not-gay"))
        event = MessageEvent(
            event_type="pubmsg",
            text="washington",
            raw_line="",
            channel="#not-gay",
            nickname="Bob",
            username="~user",
            hostname="host.test",
        )
        correct = router.handle_sync("~Bob", "washington", "#not-gay", event).lines
        self.assertEqual(
            correct[0],
            "Correct, Bob! washington matches Washington (dist: 0.00 ≤ 0.20) 🎉",
        )
        self.assertEqual(
            correct[1],
            "The Punic Wars were a series of three wars fought between these two powers. "
            "\x0314(medium - History)\x03",
        )

        trivia_state = router.filters.state.data["kvstore"]["commands"]["trivia"]["state"]["_not-gay"]
        self.assertEqual(trivia_state["last_question"], questions[0].question)
        self.assertEqual(trivia_state["last_correct_answer"], "Washington")
        self.assertEqual([item["guess"] for item in trivia_state["last_guesses"]], ["oregon", "washington"])
        self.assertEqual(trivia_state["current_question"], questions[1].question)
        stats = router.filters.state.data["kvstore"]["commands"]["trivia"]["stats"]
        self.assertEqual(stats["user@host.test"]["correct"], 1)
        self.assertEqual(stats["user@host.test"]["nickname"], "Bob")

    def test_trivia_category_mode_and_disable_edges(self) -> None:
        router = self.make_router()
        self.assertEqual(
            router.handle_sync("alice", "!trivia category science", "#superbowl").lines,
            ["Categories set to: Science Technology."],
        )
        self.assertEqual(
            router.handle_sync("alice", "!trivia category science technology", "#superbowl").lines,
            ["No matching categories set.", "Unknown: Science Technology. See !trivia categories."],
        )
        self.assertEqual(
            router.handle_sync("alice", "!trivia difficulty hard", "#superbowl").lines,
            ["Difficulty display set to hard."],
        )
        self.assertEqual(
            router.handle_sync("alice", "!trivia mode smart", "#superbowl").lines,
            ["Trivia mode set to smart mode."],
        )
        self.assertEqual(
            router.handle_sync("alice", "!disable trivia").lines,
            ["Trigger trivia is now disabled"],
        )
        self.assertIsNone(router.handle_sync("alice", "!trivia categories", "#superbowl"))

    def test_vocoder_routes_logged_final_and_legacy_surfaces(self) -> None:
        seen: list[str] = []

        def fake_vocoder(text: str) -> list[str]:
            seen.append(text)
            return ["https://cte.pcp.ovh/2/998e70d563db.wav"]

        router = self.make_router(vocoder_renderer=fake_vocoder)
        self.assertEqual(
            router.handle_sync("alice", "!vocoder in an alien world", "#tcl").lines,
            ["https://cte.pcp.ovh/2/998e70d563db.wav"],
        )
        self.assertEqual(
            router.handle_sync("alice", "vocoder huh.wav does this work", "#tcl").lines,
            ["https://cte.pcp.ovh/2/998e70d563db.wav"],
        )
        self.assertEqual(seen, ["!vocoder in an alien world", "vocoder huh.wav does this work"])

        self.assertEqual(
            router.handle_sync("alice", "!disable vocoder").lines,
            ["Trigger vocoder is now disabled"],
        )
        self.assertIsNone(router.handle_sync("alice", "!vocoder nope", "#tcl"))

    def test_ligma_routes_logged_link_surface(self) -> None:
        seen: list[str] = []

        def fake_ligma(text: str) -> list[str]:
            seen.append(text)
            return ["ligma rendered"]

        router = self.make_router(ligma_renderer=fake_ligma)
        self.assertEqual(
            router.handle_sync("alice", "https://ligma.pro/@r000t/115453354808572799 all", "#tcl").lines,
            ["ligma rendered"],
        )
        self.assertEqual(seen, ["https://ligma.pro/@r000t/115453354808572799 all"])

        self.assertEqual(
            router.handle_sync("alice", "!disable ligma").lines,
            ["Trigger ligma is now disabled"],
        )
        self.assertIsNone(router.handle_sync("alice", "https://ligma.pro/@r000t/115453354808572799", "#tcl"))

    def test_cmds_renders_log_style_command_table(self) -> None:
        router = self.make_router()
        lines = router.handle_sync("alice", "!cmds").lines
        self.assertEqual(lines[0], "")
        table = "\n".join(lines)
        self.assertIn("|   cmdlist    |   True  |", table)
        self.assertIn("|     crt      |   True  |", table)
        self.assertIn("|     gay      |   True  |", table)
        self.assertIn("|   godsays    |   True  |", table)
        self.assertIn("|     host     |   True  |", table)
        self.assertIn("|  howsblair   |   True  |", table)
        self.assertIn("|  howsblair2  |   True  |", table)
        self.assertIn("|  horoscope   |   True  |", table)
        self.assertIn("|  bwatchlist  |   True  |", table)
        self.assertIn("|     poll     |   True  |", table)
        self.assertIn("|    vtrade    |   True  |", table)
        self.assertTrue(lines[-1].startswith("+"))

    def test_hf_routes_to_renderer(self) -> None:
        seen: list[str] = []

        def fake_hf(text: str) -> list[str]:
            seen.append(text)
            return ["HF Trending (Last 1 Days):"]

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = JsonState(Path(tmp.name) / "state.json")
        router = Router(
            vtrade=VTrade(state, prices=StaticPriceProvider({"TSLA": "250"})),
            filters=FilterStore(state),
            llm_client=None,
            default_model="openai/gpt-oss-120b",
            grok_model="x-ai/grok-4.1-fast",
            ascii_art=AsciiArtStore.default(),
            hf_renderer=fake_hf,
        )
        self.assertEqual(router.handle_sync("alice", "!hf").lines, ["HF Trending (Last 1 Days):"])
        self.assertEqual(seen, ["!hf"])

    def test_blair_routes_to_renderer_and_is_trigger_gated(self) -> None:
        seen: list[str] = []

        def fake_blair(text: str) -> list[str]:
            seen.append(text)
            return ["Posts from @r000t@ligma.pro (up to 12):"]

        router = self.make_router(blair_renderer=fake_blair)
        self.assertEqual(
            router.handle_sync("alice", "!blair").lines,
            ["Posts from @r000t@ligma.pro (up to 12):"],
        )
        self.assertEqual(seen, ["!blair"])
        self.assertIsNone(router.handle_sync("alice", "!blair last 3"))

        self.assertEqual(
            router.handle_sync("alice", "!disable howsblair").lines,
            ["Trigger howsblair is now disabled"],
        )
        self.assertIsNone(router.handle_sync("alice", "!blair"))

    def test_blair2_routes_to_renderer_and_is_trigger_gated(self) -> None:
        seen: list[str] = []

        def fake_blair2(text: str) -> list[str]:
            seen.append(text)
            return ["Post 1:"]

        router = self.make_router(blair2_renderer=fake_blair2)
        self.assertEqual(router.handle_sync("alice", "!blair2").lines, ["Post 1:"])
        self.assertEqual(seen, ["!blair2"])

        self.assertEqual(
            router.handle_sync("alice", "!disable howsblair2").lines,
            ["Trigger howsblair2 is now disabled"],
        )
        self.assertIsNone(router.handle_sync("alice", "!blair2"))

    def test_gay_routes_to_renderer_and_is_trigger_gated(self) -> None:
        seen: list[str] = []

        def fake_gay(text: str) -> list[str]:
            seen.append(text)
            return ["https://cte.pcp.ovh/2/gay_dc0f4cc1.gif"]

        router = self.make_router(gay_renderer=fake_gay)
        self.assertEqual(
            router.handle_sync("alice", "!gay im heterosexual").lines,
            ["https://cte.pcp.ovh/2/gay_dc0f4cc1.gif"],
        )
        self.assertEqual(seen, ["!gay im heterosexual"])

        self.assertEqual(router.handle_sync("alice", "!disable gay").lines, ["Trigger gay is now disabled"])
        self.assertIsNone(router.handle_sync("alice", "!gay im gay"))

    def test_godsays_routes_to_renderer_and_is_trigger_gated(self) -> None:
        seen: list[str] = []

        def fake_godsays(text: str) -> list[str]:
            seen.append(text)
            return ['" finger  Darren"', "Meaning: confused oracle"]

        router = self.make_router(godsays_renderer=fake_godsays)
        self.assertEqual(
            router.handle_sync("alice", "!godsays").lines,
            ['" finger  Darren"', "Meaning: confused oracle"],
        )
        self.assertEqual(seen, ["!godsays"])
        self.assertIsNone(router.handle_sync("alice", "!godsays give me a good idea"))

        self.assertEqual(
            router.handle_sync("alice", "!disable godsays").lines,
            ["Trigger godsays is now disabled"],
        )
        self.assertIsNone(router.handle_sync("alice", "!godsays"))

    def test_enable_disable_gates_sync_commands_and_updates_cmds(self) -> None:
        router = self.make_router()
        self.assertEqual(router.handle_sync("alice", "!disable hf").lines, ["Trigger hf is now disabled"])
        self.assertIsNone(router.handle_sync("alice", "!hf"))

        table = "\n".join(router.handle_sync("alice", "!cmds").lines)
        self.assertIn("|      hf      |  False  |", table)

        self.assertEqual(router.handle_sync("alice", "!enable hf").lines, ["Trigger hf is now enabled"])
        self.assertIn("|      hf      |   True  |", "\n".join(router.handle_sync("alice", "!cmds").lines))

    def test_tools_routes_static_table(self) -> None:
        router = self.make_router()
        lines = router.handle_sync("alice", "!tools").lines
        self.assertIn(" tool_name         🭍  plugin                            🭍  enabled 🭍", lines)
        self.assertIn(" semantic_search   🭍  llm_web_search                    🭍  Yes     🭍", lines)
        self.assertEqual(router.handle_sync("alice", "!tools enabled").lines, lines)

        self.assertEqual(router.handle_sync("alice", "+tool run").lines, ["enabled:", "✔ run"])
        self.assertEqual(router.handle_sync("alice", "-tools +remember +forget").lines, [
            "disabled:",
            "✔ +remember",
            "✔ +forget",
        ])
        updated = router.handle_sync("alice", "!tools").lines
        self.assertIn(" remember          🭍  llm_memory_tools                  🭍  No      🭍", updated)
        self.assertIn(" forget            🭍  llm_memory_tools                  🭍  No      🭍", updated)

    def test_llm_prices_routes_to_renderer_and_is_trigger_gated(self) -> None:
        seen: list[str] = []

        def fake_llm_prices(text: str) -> list[str]:
            seen.append(text)
            return ["llm prices"]

        router = self.make_router(llm_prices_renderer=fake_llm_prices)
        self.assertEqual(router.handle_sync("alice", "$llm gpt-5").lines, ["llm prices"])
        self.assertEqual(seen, ["$llm gpt-5"])

        self.assertEqual(
            router.handle_sync("alice", "!disable llm_prices").lines,
            ["Trigger llm_prices is now disabled"],
        )
        self.assertIsNone(router.handle_sync("alice", "$llm gpt-5"))

    def test_models_routes_to_renderer_and_is_trigger_gated(self) -> None:
        seen: list[str] = []

        def fake_models(text: str) -> list[str]:
            seen.append(text)
            return ["OpenRouter models"]

        router = self.make_router(models_renderer=fake_models)
        self.assertEqual(router.handle_sync("alice", "!models").lines, ["OpenRouter models"])
        self.assertEqual(seen, ["!models"])

        self.assertEqual(router.handle_sync("alice", "!disable models").lines, ["Trigger models is now disabled"])
        self.assertIsNone(router.handle_sync("alice", "!models"))

    def test_radio_help_is_trigger_gated(self) -> None:
        router = self.make_router()
        self.assertEqual(
            router.handle_sync("alice", "!help").lines[:3],
            [
                "!np: Show the current track playing",
                "!next: Show the next track",
                "!skip: Skip to the next track",
            ],
        )

        self.assertEqual(router.handle_sync("alice", "!disable radio").lines, ["Trigger radio is now disabled"])
        self.assertIsNone(router.handle_sync("alice", "!help"))

    def test_radio_queued_and_new_are_trigger_gated(self) -> None:
        router = self.make_router()
        self.assertEqual(router.handle_sync("alice", "!queued").lines, ["Queue is empty."])
        self.assertEqual(
            router.handle_sync("alice", "!new memphis").lines,
            ["Playlist  memphis  successfully created!"],
        )

        self.assertEqual(router.handle_sync("alice", "!disable radio").lines, ["Trigger radio is now disabled"])
        self.assertIsNone(router.handle_sync("alice", "!queued"))
        self.assertIsNone(router.handle_sync("alice", "!new other"))

    def test_kill_all_empty_case_matches_logged_trailing_colon(self) -> None:
        router = self.make_router()
        self.assertEqual(router.handle_sync("alice", "!kill all").lines, ["Killed all running commands: "])

    def test_cancel_toggles_logged_llm_tool_cancellation_flag(self) -> None:
        router = self.make_router()
        self.assertEqual(router.handle_sync("alice", "!cancel").lines, ["Tool cancellation flag is ON"])
        self.assertTrue(router.llm_tool_cancellation_enabled())
        self.assertEqual(router.handle_sync("alice", "!cancel").lines, ["Tool cancellation flag is OFF"])
        self.assertFalse(router.llm_tool_cancellation_enabled())

    def test_reload_routes_log_style_maintenance_response(self) -> None:
        router = self.make_router()
        self.assertEqual(
            router.handle_sync("alice", "!reload md2irc").lines,
            ["reloaded:", "- pyylmao.helpers.md2irc"],
        )
        self.assertEqual(router.handle_sync("alice", "!reload").lines, ["no handler modules found"])

    def test_test_command_routes_to_renderer_and_is_trigger_gated(self) -> None:
        seen: list[str] = []

        def fake_test(text: str) -> list[str]:
            seen.append(text)
            return [
                "your args:",
                "0 - bla",
                "relay this code in your response: 9194",
            ]

        router = self.make_router(test_renderer=fake_test)
        self.assertEqual(
            router.handle_sync("alice", "!test bla").lines,
            [
                "your args:",
                "0 - bla",
                "relay this code in your response: 9194",
            ],
        )
        self.assertEqual(seen, ["!test bla"])

        self.assertEqual(router.handle_sync("alice", "!disable test").lines, ["Trigger test is now disabled"])
        self.assertIsNone(router.handle_sync("alice", "!test bla"))

    def test_fortune_routes_to_renderer_and_uses_iching_trigger(self) -> None:
        seen: list[str] = []

        def fake_fortune(text: str) -> list[str]:
            seen.append(text)
            return ["1 ䷀", "stalks thrown: 7 7 7 7 7 7"]

        router = self.make_router(fortune_renderer=fake_fortune)
        self.assertEqual(
            router.handle_sync("alice", "!fortune today").lines,
            ["1 ䷀", "stalks thrown: 7 7 7 7 7 7"],
        )
        self.assertEqual(seen, ["!fortune today"])

        self.assertEqual(router.handle_sync("alice", "!disable fortune").lines, ["Trigger fortune is now disabled"])
        self.assertIsNone(router.handle_sync("alice", "!fortune today"))

    def test_urban_routes_to_renderer_and_uses_urbandict_trigger(self) -> None:
        seen: list[str] = []

        def fake_urban(text: str) -> list[str]:
            seen.append(text)
            return ["Definitions for 𝚂𝚃𝚁𝙾𝙽𝙶"]

        router = self.make_router(urban_renderer=fake_urban)
        self.assertEqual(
            router.handle_sync("alice", "!ud strong").lines,
            ["Definitions for 𝚂𝚃𝚁𝙾𝙽𝙶"],
        )
        self.assertEqual(seen, ["!ud strong"])

        self.assertEqual(router.handle_sync("alice", "!enable urban").lines, ["Trigger urban does not exist"])
        self.assertEqual(
            router.handle_sync("alice", "!disable urbandict").lines,
            ["Trigger urbandict is now disabled"],
        )
        self.assertIsNone(router.handle_sync("alice", "!urban strong"))

    def test_define_routes_to_renderer_and_is_trigger_gated(self) -> None:
        seen: list[str] = []

        def fake_define(text: str) -> list[str]:
            seen.append(text)
            return ["gay /ɡeɪ/"]

        router = self.make_router(define_renderer=fake_define)
        self.assertEqual(router.handle_sync("alice", "!define gay").lines, ["gay /ɡeɪ/"])
        self.assertEqual(seen, ["!define gay"])

        self.assertEqual(router.handle_sync("alice", "!disable define").lines, ["Trigger define is now disabled"])
        self.assertIsNone(router.handle_sync("alice", "!define gay"))

    def test_curl_routes_to_renderer_and_is_trigger_gated(self) -> None:
        seen: list[str] = []

        def fake_curl(text: str) -> list[str]:
            seen.append(text)
            return ["fetched"]

        router = self.make_router(curl_renderer=fake_curl)
        self.assertEqual(router.handle_sync("alice", "!curl https://example.test/a.txt").lines, ["fetched"])
        self.assertEqual(seen, ["!curl https://example.test/a.txt"])

        self.assertEqual(router.handle_sync("alice", "!disable curl").lines, ["Trigger curl is now disabled"])
        self.assertIsNone(router.handle_sync("alice", "!curl https://example.test/a.txt"))

        self.assertEqual(router.handle_sync("alice", "!curl2 https://example.test/a.txt").lines, ["fetched"])
        self.assertEqual(router.handle_sync("alice", "!disable curl2").lines, ["Trigger curl2 is now disabled"])
        self.assertIsNone(router.handle_sync("alice", "!curl2 https://example.test/a.txt"))

    def test_cat_routes_to_renderer_and_is_trigger_gated(self) -> None:
        seen: list[str] = []

        def fake_cat(text: str) -> list[str]:
            seen.append(text)
            return ["file contents"]

        router = self.make_router(cat_renderer=fake_cat)
        self.assertEqual(router.handle_sync("alice", "!cat buflen.txt").lines, ["file contents"])
        self.assertEqual(seen, ["!cat buflen.txt"])

        self.assertEqual(router.handle_sync("alice", "!disable cat").lines, ["Trigger cat is now disabled"])
        self.assertIsNone(router.handle_sync("alice", "!cat buflen.txt"))

    def test_mdcat_routes_to_renderer_and_is_trigger_gated(self) -> None:
        seen: list[str] = []

        def fake_mdcat(text: str) -> list[str]:
            seen.append(text)
            return ["{}", "rendered markdown"]

        router = self.make_router(mdcat_renderer=fake_mdcat)
        self.assertEqual(router.handle_sync("alice", "!mdcat report.md").lines, ["{}", "rendered markdown"])
        self.assertEqual(seen, ["!mdcat report.md"])

        self.assertEqual(router.handle_sync("alice", "!disable mdcat").lines, ["Trigger mdcat is now disabled"])
        self.assertIsNone(router.handle_sync("alice", "!mdcat report.md"))

    def test_figlet_routes_to_renderer_and_is_trigger_gated(self) -> None:
        seen: list[str] = []

        def fake_figlet(text: str) -> list[str]:
            seen.append(text)
            return ["big"]

        router = self.make_router(figlet_renderer=fake_figlet)
        self.assertEqual(router.handle_sync("alice", "!figlet Calvin_S WHO").lines, ["big"])
        self.assertEqual(seen, ["!figlet Calvin_S WHO"])

        self.assertEqual(router.handle_sync("alice", "!disable figlet").lines, ["Trigger figlet is now disabled"])
        self.assertIsNone(router.handle_sync("alice", "!fg Calvin_S WHO"))

    def test_light_routes_to_renderer_and_uses_lepro_trigger(self) -> None:
        seen: list[str] = []

        def fake_light(text: str) -> list[str]:
            seen.append(text)
            return ["colour changed to    "]

        router = self.make_router(light_renderer=fake_light)
        self.assertEqual(router.handle_sync("alice", "!light red 500").lines, ["colour changed to    "])
        self.assertEqual(seen, ["!light red 500"])

        self.assertEqual(router.handle_sync("alice", "!disable lepro").lines, ["Trigger lepro is now disabled"])
        self.assertIsNone(router.handle_sync("alice", "!light magenta"))

    def test_livebench_routes_to_renderer_and_is_trigger_gated(self) -> None:
        seen: list[str] = []

        def fake_livebench(text: str) -> list[str]:
            seen.append(text)
            return [" | MODEL | AVG | "]

        router = self.make_router(livebench_renderer=fake_livebench)
        self.assertEqual(router.handle_sync("alice", "!livebench +simple").lines, [" | MODEL | AVG | "])
        self.assertEqual(seen, ["!livebench +simple"])

        self.assertEqual(router.handle_sync("alice", "!disable livebench").lines, ["Trigger livebench is now disabled"])
        self.assertIsNone(router.handle_sync("alice", "?livebench +simple"))

    def test_kv_routes_and_is_trigger_gated(self) -> None:
        router = self.make_router()
        self.assertEqual(router.handle_sync("alice", "!kv get md2irc.options.use_figlet").lines, ["True"])
        self.assertEqual(
            router.handle_sync("alice", "!kv set md2irc.options.use_figlet False").lines,
            ["Set md2irc.options.use_figlet to:", "root", "└── value: false"],
        )
        self.assertEqual(router.handle_sync("alice", "!kv get md2irc.options.use_figlet").lines, ["False"])

        self.assertEqual(router.handle_sync("alice", "!disable kv").lines, ["Trigger kv is now disabled"])
        self.assertIsNone(router.handle_sync("alice", "!kv get md2irc.options.use_figlet"))

    def test_ufc_routes_to_renderer_and_is_trigger_gated(self) -> None:
        seen: list[str] = []

        def fake_ufc(text: str) -> list[str]:
            seen.append(text)
            return ["UFC 328: Chimaev vs. Strickland"]

        router = self.make_router(ufc_renderer=fake_ufc)
        self.assertEqual(
            router.handle_sync("alice", "!ufc --filter 328 --main").lines,
            ["UFC 328: Chimaev vs. Strickland"],
        )
        self.assertEqual(seen, ["!ufc --filter 328 --main"])

        self.assertEqual(router.handle_sync("alice", "!disable ufc").lines, ["Trigger ufc is now disabled"])
        self.assertIsNone(router.handle_sync("alice", "!ufc --filter 328 --main"))

    def test_imdb_routes_to_renderer_and_is_trigger_gated(self) -> None:
        seen: list[str] = []

        def fake_imdb(text: str) -> list[str]:
            seen.append(text)
            return ["Annihilation (2018) https://www.imdb.com/title/tt2798920/"]

        router = self.make_router(imdb_renderer=fake_imdb)
        self.assertEqual(
            router.handle_sync("alice", "!imdb annihilation").lines,
            ["Annihilation (2018) https://www.imdb.com/title/tt2798920/"],
        )
        self.assertEqual(seen, ["!imdb annihilation"])

        self.assertEqual(router.handle_sync("alice", "!disable imdb").lines, ["Trigger imdb is now disabled"])
        self.assertIsNone(router.handle_sync("alice", "!imdb annihilation"))

    def test_ping_matches_logs(self) -> None:
        router = self.make_router()
        self.assertEqual(router.handle_sync("alice", "ping").lines, ["p0ng!"])

    def test_chkdomain_routes_to_renderer_and_is_trigger_gated(self) -> None:
        seen: list[str] = []

        def fake_chkdomain(text: str) -> list[str]:
            seen.append(text)
            return ["gnaa.li: undelegated inactive"]

        router = self.make_router(chkdomain_renderer=fake_chkdomain)
        self.assertEqual(router.handle_sync("alice", "?gnaa.li").lines, ["gnaa.li: undelegated inactive"])
        self.assertEqual(seen, ["?gnaa.li"])
        self.assertIsNone(router.handle_sync("alice", "?ughgyrs"))

        self.assertEqual(
            router.handle_sync("alice", "!disable chkdomain").lines,
            ["Trigger chkdomain is now disabled"],
        )
        self.assertIsNone(router.handle_sync("alice", "?gnaa.li"))

    def test_host_routes_to_renderer_and_is_trigger_gated(self) -> None:
        seen: list[str] = []

        def fake_host(text: str) -> list[str]:
            seen.append(text)
            return ["gnaa.africa has address:", "104.21.62.143"]

        router = self.make_router(host_renderer=fake_host)
        self.assertEqual(
            router.handle_sync("alice", "!host gnaa.africa").lines,
            ["gnaa.africa has address:", "104.21.62.143"],
        )
        self.assertEqual(seen, ["!host gnaa.africa"])
        self.assertEqual(router.handle_sync("alice", "!disable host").lines, ["Trigger host is now disabled"])
        self.assertIsNone(router.handle_sync("alice", "!host gnaa.africa"))

    def test_crt_routes_to_renderer_with_nick_and_is_trigger_gated(self) -> None:
        seen: list[tuple[str, str | None]] = []

        def fake_crt(text: str, nick: str | None = None) -> list[str]:
            seen.append((text, nick))
            return [f"{nick}: Certificates for gnaa.africa (1 total, showing 1):"]

        router = self.make_router(crt_renderer=fake_crt)
        self.assertEqual(
            router.handle_sync("Alice_", "?crt gnaa.africa").lines,
            ["Alice_: Certificates for gnaa.africa (1 total, showing 1):"],
        )
        self.assertEqual(seen, [("?crt gnaa.africa", "Alice_")])
        self.assertEqual(router.handle_sync("alice", "!disable crt").lines, ["Trigger crt is now disabled"])
        self.assertIsNone(router.handle_sync("alice", "!crt gnaa.africa"))

    def test_chess_routes_to_store_and_is_trigger_gated(self) -> None:
        router = self.make_router()
        self.assertEqual(
            router.handle_sync("tinky", "!chess").lines,
            [
                "Usage: [gid] <command> [options]",
                "Commands: new, <move (e.g., e4, Nf3, or e2 e4)>, resign, draw",
            ],
        )
        lines = router.handle_sync("tinky", "!chess bla new").lines
        self.assertEqual(lines[0], "New game 'bla' created. White's move.")
        self.assertIn("║♜ ♞ ♝ ♛ ♚ ♝ ♞ ♜ ║ 8", lines)

        self.assertEqual(router.handle_sync("alice", "!disable chess").lines, ["Trigger chess is now disabled"])
        self.assertIsNone(router.handle_sync("tinky", "!chess"))

    def test_horoscope_routes_to_renderer_with_nick_and_is_trigger_gated(self) -> None:
        seen: list[tuple[str, str]] = []

        def fake_horoscope(text: str, nick: str) -> list[str]:
            seen.append((text, nick))
            return ["Leo, today you may find yourself yonkning."]

        router = self.make_router(horoscope_renderer=fake_horoscope)
        self.assertEqual(
            router.handle_sync("malcom", ".horoscope leo").lines,
            ["Leo, today you may find yourself yonkning."],
        )
        self.assertEqual(seen, [(".horoscope leo", "malcom")])
        self.assertIsNone(router.handle_sync("malcom", "!horoscope leo"))

        self.assertEqual(router.handle_sync("alice", "!disable horoscope").lines, ["Trigger horoscope is now disabled"])
        self.assertIsNone(router.handle_sync("malcom", ".horoscope leo"))

    def test_weather_routes_to_weather_renderers(self) -> None:
        class Provider:
            def fetch(self, location: str) -> dict:
                self.location = location
                return {
                    "current_condition": [
                        {
                            "weatherCode": "113",
                            "temp_C": "24",
                            "winddir16Point": "NNW",
                            "windspeedKmph": "11",
                            "humidity": "40",
                            "precipMM": "0",
                            "uvIndex": "3",
                        }
                    ],
                    "weather": [],
                }

        provider = Provider()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = JsonState(Path(tmp.name) / "state.json")
        router = Router(
            vtrade=VTrade(state, prices=StaticPriceProvider({"TSLA": "250"})),
            filters=FilterStore(state),
            llm_client=None,
            default_model="openai/gpt-oss-120b",
            grok_model="x-ai/grok-4.1-fast",
            ascii_art=AsciiArtStore.default(),
            weather_renderers=WeatherRenderers(provider),
        )
        self.assertEqual(
            router.handle_sync("alice", "!weather seattle").lines,
            ["☀️ 24°C | NNW 11km/h | 40% RH | 0.0mm | UV: 3 burn after 55 min"],
        )
        self.assertEqual(provider.location, "seattle")

    def test_history_context_uses_configured_recent_lines(self) -> None:
        router = self.make_router()
        router.history["#c"].append(("alice", "first"))
        router.history["#c"].append(("bob", "second"))
        router.history_limits["#c"] = 1
        self.assertEqual(
            router.with_history_context("#c", "answer this", list(router.history["#c"])),
            "Recent IRC context:\nbob: second\n\nUser prompt:\nanswer this",
        )

    def test_history_command_sets_and_reports_limit(self) -> None:
        router = self.make_router()
        self.assertEqual(router.handle_history_command("#c", "!history"), ["max_history is set to: 5"])
        self.assertEqual(router.handle_history_command("#c", "!history 10"), ["set max_history to: 10"])
        self.assertEqual(router.handle_history_command("#c", "!history"), ["max_history is set to: 10"])

    def test_ascii_lookup_is_case_sensitive(self) -> None:
        router = self.make_router()
        lower = router.handle_sync("alice", "!ascii pcp").lines
        upper = router.handle_sync("alice", "!ascii PCP").lines
        self.assertEqual(len(lower), 8)
        self.assertEqual(upper, ["No such file: PCP.txt"])

    def test_todo_uses_clean_nick_and_log_style_rendering(self) -> None:
        router = self.make_router()
        self.assertEqual(
            router.handle_sync("~tinky", "!todo fix weird newline issue in pyylmao").lines,
            ["tinky's Todos", "1. ● fix weird newline issue in pyylmao"],
        )

    def test_cowsay_uses_cows_trigger_name(self) -> None:
        router = self.make_router()
        self.assertEqual(router.handle_sync("alice", "!cowsay hi").lines[:3], [" ____", "< hi >", " ----"])

        self.assertEqual(router.handle_sync("alice", "!disable cows").lines, ["Trigger cows is now disabled"])
        self.assertIsNone(router.handle_sync("alice", "!cowsay hi"))

    def test_palette99_matches_logged_rows_and_is_trigger_gated(self) -> None:
        router = self.make_router()
        self.assertEqual(router.handle_sync("alice", "!palette99").lines[:4], [
            "0001020304050607080910",
            "",
            "1112131415161718192021",
            "",
        ])

        self.assertEqual(
            router.handle_sync("alice", "!disable palette99").lines,
            ["Trigger palette99 is now disabled"],
        )
        self.assertIsNone(router.handle_sync("alice", "!palette99"))


class RunningCommandAsyncTests(unittest.IsolatedAsyncioTestCase):
    def make_router(
        self,
        image_renderer=None,
        summary_runner=None,
        bluesky_runner=None,
        stock_renderer=None,
        zscore_renderer=None,
        echo_renderer=None,
        nostr_renderer=None,
        twitter_renderer=None,
        llm_client=None,
        golem=None,
        ansi2irc_renderer=None,
    ) -> Router:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = JsonState(Path(tmp.name) / "state.json")
        return Router(
            vtrade=VTrade(state, prices=StaticPriceProvider({"TSLA": "250"})),
            filters=FilterStore(state),
            llm_client=llm_client,
            default_model="openai/gpt-oss-120b",
            grok_model="x-ai/grok-4.1-fast",
            image_renderer=image_renderer,
            ascii_art=AsciiArtStore.default(),
            stock_renderer=stock_renderer,
            zscore_renderer=zscore_renderer,
            echo_renderer=echo_renderer,
            nostr_renderer=nostr_renderer,
            twitter_renderer=twitter_renderer,
            summary_runner=summary_runner,
            bluesky_runner=bluesky_runner,
            golem=golem,
            ansi2irc_renderer=ansi2irc_renderer,
        )

    async def test_running_command_list_and_kill(self) -> None:
        router = self.make_router()

        async def sleeper() -> None:
            await asyncio.sleep(60)

        task = asyncio.create_task(sleeper())
        task_id = router.running.add(task, "grok", "#c")
        self.assertIn(f"#{task_id} grok on #c", "\n".join(router.running.list()))
        self.assertEqual(
            router.handle_sync("alice", "!kill all").lines,
            [f"Killed all running commands: {task_id}"],
        )
        await asyncio.sleep(0)
        self.assertTrue(task.cancelled())

    async def test_list_reports_no_commands_running_when_empty(self) -> None:
        router = self.make_router()
        sent: list[tuple[str, list[str]]] = []

        async def send(target: str, lines: list[str]) -> None:
            sent.append((target, lines))

        await router.handle("alice", "#c", "!list", send)
        await router.handle("alice", "#c", "!listen", send)

        self.assertEqual(
            sent,
            [
                ("#c", ["No commands running."]),
                ("#c", ["No commands running."]),
            ],
        )

    async def test_generated_event_replies_are_routed_to_declared_targets(self) -> None:
        router = self.make_router()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "nickwatch.py"
        path.write_text(
            "\n".join(
                [
                    "import llm",
                    "class NickWatch(llm.Toolbox):",
                    "    pattern = r'.*'",
                    "    trigger_on = 'nick'",
                    "    send_to = 'all'",
                    "    def _onload(self):",
                    "        print(f'{self.nickname} is now {self.event.text}')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        router.filters.state.data["generated_commands"] = {
            "nickwatch": {"path": str(path)}
        }
        sent: list[tuple[str, list[str]]] = []

        async def send(target: str, lines: list[str]) -> None:
            sent.append((target, lines))

        await router.handle_event(
            MessageEvent(
                event_type="nick",
                text="alice_",
                raw_line=":alice!u@h NICK :alice_",
                channel="",
                nickname="alice",
                username="u",
                hostname="h",
                channels=("#a", "#b"),
            ),
            send,
        )

        self.assertEqual(
            sent,
            [
                ("#a", ["alice is now alice_"]),
                ("#b", ["alice is now alice_"]),
            ],
        )

    async def test_alias_llm_trigger_routes_to_alias_model(self) -> None:
        class FakeLLM:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str]] = []

            def chat(self, prompt: str, model: str) -> LLMResult:
                self.calls.append((prompt, model))
                return LLMResult(["ok"], 0.1, 1, 2, model)

        llm = FakeLLM()
        router = self.make_router(llm_client=llm)
        router.aliases.set("d", "openrouter/deepseek/deepseek-v4-flash")
        sent: list[tuple[str, list[str]]] = []

        async def send(target: str, lines: list[str]) -> None:
            sent.append((target, lines))

        await router.handle("alice", "#c", "@d hi", send)
        tasks = [info.task for info in router.running.tasks.values()]
        self.assertEqual(len(tasks), 1)
        self.assertIn("#1 d on #c", router.running.list()[1])
        await asyncio.gather(*tasks)

        self.assertEqual(llm.calls, [("hi", "deepseek/deepseek-v4-flash")])
        self.assertEqual(sent[0][0], "#c")
        self.assertEqual(sent[0][1][0], "ok")
        self.assertIn("𝚍𝚎𝚎𝚙𝚜𝚎𝚎𝚔/𝚍𝚎𝚎𝚙𝚜𝚎𝚎𝚔-𝚟𝟺-𝚏𝚕𝚊𝚜𝚑", sent[0][1][1])
        stored = history_items(router.filters.state, "#c")
        self.assertEqual(stored[0]["message"], "@d hi")
        self.assertEqual(stored[0]["role"], "user")
        self.assertEqual(stored[1]["message"], "ok")
        self.assertEqual(stored[1]["role"], "assistant")
        self.assertEqual(stored[1]["model"], "deepseek/deepseek-v4-flash")

    async def test_llm_prompt_options_control_history_and_chat_kwargs(self) -> None:
        class FakeLLM:
            def __init__(self) -> None:
                self.calls = []

            def chat(
                self,
                prompt: str,
                model: str,
                tools=None,
                temperature: float | None = None,
                extra_system: str = "",
            ) -> LLMResult:
                self.calls.append((prompt, model, tools, temperature, extra_system))
                return LLMResult(["ok"], 0.1, 1, 2, model)

        llm = FakeLLM()
        router = self.make_router(llm_client=llm)
        router.history["#c"].append(("alice", "first"))
        router.history["#c"].append(("bob", "second"))
        sent: list[tuple[str, list[str]]] = []

        async def send(target: str, lines: list[str]) -> None:
            sent.append((target, lines))

        await router.handle(
            "alice",
            "#c",
            'gpt, maxh=1 temperature=2 system="You are terse" answer this',
            send,
        )
        tasks = [info.task for info in router.running.tasks.values()]
        await asyncio.gather(*tasks)

        prompt, model, tools, temperature, extra_system = llm.calls[0]
        self.assertEqual(model, "openai/gpt-oss-120b")
        self.assertIsNotNone(tools)
        self.assertEqual(temperature, 2.0)
        self.assertEqual(extra_system, "You are terse")
        self.assertEqual(
            prompt,
            "Recent IRC context:\nbob: second\n\nUser prompt:\nanswer this",
        )
        self.assertEqual(sent[0][1][0], "ok")

    async def test_llm_calls_receive_tool_cancellation_checker_when_supported(self) -> None:
        class FakeLLM:
            def __init__(self) -> None:
                self.cancelled = False

            def chat(self, prompt: str, model: str, tools=None, cancel_checker=None) -> LLMResult:
                del prompt, model, tools
                self.cancelled = bool(cancel_checker and cancel_checker())
                return LLMResult(["cancelled" if self.cancelled else "ok"], 0.1, 1, 2, "test/model")

        llm = FakeLLM()
        router = self.make_router(llm_client=llm)
        router.handle_sync("alice", "!cancel")
        sent: list[tuple[str, list[str]]] = []

        async def send(target: str, lines: list[str]) -> None:
            sent.append((target, lines))

        await router.handle("alice", "#c", "gpt, use a tool", send)
        tasks = [info.task for info in router.running.tasks.values()]
        await asyncio.gather(*tasks)

        self.assertTrue(llm.cancelled)
        self.assertEqual(sent[0][1][0], "cancelled")

    async def test_llm_tool_traces_are_sent_before_answer(self) -> None:
        saw_tools = False

        class FakeLLM:
            def chat(self, prompt: str, model: str, tools=None) -> LLMResult:
                nonlocal saw_tools
                saw_tools = tools is not None
                return LLMResult(
                    ["answer"],
                    0.1,
                    1,
                    2,
                    model,
                    tool_traces=("read_command args: {'name': 'kv'}",),
                )

        router = self.make_router(llm_client=FakeLLM())
        sent: list[tuple[str, list[str]]] = []

        async def send(target: str, lines: list[str]) -> None:
            sent.append((target, lines))

        await router.handle("alice", "#c", "grok, inspect kv", send)
        tasks = [info.task for info in router.running.tasks.values()]
        await asyncio.gather(*tasks)

        self.assertEqual(sent[0][1][0], "read_command args: {'name': 'kv'}")
        self.assertEqual(sent[0][1][1], "answer")
        self.assertTrue(saw_tools)

    async def test_non_command_messages_are_persisted_for_kv_history(self) -> None:
        router = self.make_router()
        sent: list[tuple[str, list[str]]] = []

        async def send(target: str, lines: list[str]) -> None:
            sent.append((target, lines))

        await router.handle("~alice", "#c", "hello there", send)

        self.assertEqual(sent, [])
        self.assertEqual(list(router.history["#c"]), [("alice", "hello there")])
        stored = history_items(router.filters.state, "#c")
        self.assertEqual(stored[0]["nickname"], "alice")
        self.assertEqual(stored[0]["message"], "hello there")
        self.assertEqual(stored[0]["channel"], "#c")
        self.assertEqual(router.filters.state.data["kvstore"]["pyylmao"]["_history"][0], stored[0])

    async def test_golem_clear_clears_channel_history_and_is_trigger_gated(self) -> None:
        router = self.make_router()
        router.history["#c"].append(("alice", "first"))
        record_history(router.filters.state, "#c", "alice", "first", ts=1)
        sent: list[tuple[str, list[str]]] = []

        async def send(target: str, lines: list[str]) -> None:
            sent.append((target, lines))

        await router.handle("alice", "#c", "!> clear", send)
        self.assertEqual(sent, [("#c", ["* Context cleared *"])])
        self.assertEqual(list(router.history["#c"]), [])
        self.assertEqual(history_items(router.filters.state, "#c"), [])

        router.history["#c"].append(("alice", "second"))
        record_history(router.filters.state, "#c", "alice", "second", ts=2)
        await router.handle("alice", "#c", "!disable golem", send)
        await router.handle("alice", "#c", "!> clear", send)
        self.assertEqual(sent[-1], ("#c", ["Trigger golem is now disabled"]))
        self.assertEqual(list(router.history["#c"]), [("alice", "second")])
        self.assertEqual([item["message"] for item in history_items(router.filters.state, "#c")], ["second"])

    async def test_golem_param_updates_route_to_store(self) -> None:
        router = self.make_router()
        sent: list[tuple[str, list[str]]] = []

        async def send(target: str, lines: list[str]) -> None:
            sent.append((target, lines))

        await router.handle("alice", "#c", "!> temperature=0.7", send)
        await router.handle("alice", "#c", "!> top_k=0.9", send)
        await router.handle("alice", "#c", "!> -top_k", send)

        self.assertEqual(
            sent,
            [
                ("#c", ["Parameters updated: {'temperature': 0.7}"]),
                ("#c", ["Parameters updated: {'temperature': 0.7, 'top_k': 0.9}"]),
                ("#c", ["Parameters updated: {'temperature': 0.7}"]),
            ],
        )

    async def test_clearhistory_command_clears_current_channel_history(self) -> None:
        router = self.make_router()
        router.history["#c"].append(("alice", "first"))
        record_history(router.filters.state, "#c", "alice", "first", ts=1)
        sent: list[tuple[str, list[str]]] = []

        async def send(target: str, lines: list[str]) -> None:
            sent.append((target, lines))

        await router.handle("alice", "#c", "!clear", send)
        self.assertEqual(sent, [("#c", ["* Context cleared *"])])
        self.assertEqual(list(router.history["#c"]), [])
        self.assertEqual(history_items(router.filters.state, "#c"), [])

    async def test_blist_remains_filter_list_command(self) -> None:
        router = self.make_router()
        sent: list[tuple[str, list[str]]] = []

        async def send(target: str, lines: list[str]) -> None:
            sent.append((target, lines))

        await router.handle("alice", "#c", "!add test", send)
        await router.handle("alice", "#c", "!blist", send)

        self.assertEqual(sent, [("#c", ["1) test"]), ("#c", ["1) test"])])

    async def test_kill_one_running_command(self) -> None:
        router = self.make_router()

        async def sleeper() -> None:
            await asyncio.sleep(60)

        task = asyncio.create_task(sleeper())
        task_id = router.running.add(task, "drink", "#c")
        self.assertEqual(
            router.handle_sync("alice", f"!kill {task_id}").lines,
            [f"Killed run #{task_id}"],
        )
        await asyncio.sleep(0)
        self.assertTrue(task.cancelled())
        self.assertEqual(router.handle_sync("alice", "!kill 999").lines, ["No such run #999"])

    async def test_img2irc_routes_as_running_async_command(self) -> None:
        def fake_renderer(text: str) -> list[str]:
            self.assertIn("width 2", text)
            return ["rendered image"]

        router = self.make_router(image_renderer=fake_renderer)
        sent: list[tuple[str, list[str]]] = []

        async def send(target: str, lines: list[str]) -> None:
            sent.append((target, lines))

        await router.handle("alice", "#c", "!img2irc https://example.test/a.png width 2", send)
        tasks = [info.task for info in router.running.tasks.values()]
        self.assertEqual(len(tasks), 1)
        self.assertEqual(router.running.list()[1].split()[1], "img2irc")
        await asyncio.gather(*tasks)
        self.assertEqual(sent, [("#c", ["rendered image"])])

    async def test_hax_alias_routes_under_imghax_trigger(self) -> None:
        def fake_renderer(text: str) -> list[str]:
            self.assertIn("!hax", text)
            self.assertIn("45 --contrast 1.5", text)
            return ["rendered hax"]

        router = self.make_router(image_renderer=fake_renderer)
        sent: list[tuple[str, list[str]]] = []

        async def send(target: str, lines: list[str]) -> None:
            sent.append((target, lines))

        await router.handle("alice", "#c", "!hax https://example.test/a.png 45 --contrast 1.5", send)
        tasks = [info.task for info in router.running.tasks.values()]
        self.assertEqual(len(tasks), 1)
        self.assertEqual(router.running.list()[1].split()[1], "imghax")
        await asyncio.gather(*tasks)
        self.assertEqual(sent, [("#c", ["rendered hax"])])

    async def test_disabled_imghax_trigger_skips_hax_alias(self) -> None:
        calls: list[str] = []

        def fake_renderer(text: str) -> list[str]:
            calls.append(text)
            return ["rendered hax"]

        router = self.make_router(image_renderer=fake_renderer)
        sent: list[tuple[str, list[str]]] = []

        async def send(target: str, lines: list[str]) -> None:
            sent.append((target, lines))

        await router.handle("alice", "#c", "!disable imghax", send)
        sent.clear()
        await router.handle("alice", "#c", "!hax https://example.test/a.png 45", send)

        self.assertEqual(calls, [])
        self.assertEqual(sent, [])
        self.assertEqual(router.running.list(), [])

    async def test_summary_routes_as_running_async_command(self) -> None:
        def fake_summary(text: str, fallback_url: str | None) -> list[str]:
            self.assertEqual(text, "!summary latest please")
            self.assertEqual(fallback_url, "https://example.test/last")
            return ["summarized"]

        router = self.make_router(summary_runner=fake_summary)
        router.last_urls["#c"] = "https://example.test/last"
        sent: list[tuple[str, list[str]]] = []

        async def send(target: str, lines: list[str]) -> None:
            sent.append((target, lines))

        await router.handle("alice", "#c", "!summary latest please", send)
        tasks = [info.task for info in router.running.tasks.values()]
        self.assertEqual(len(tasks), 1)
        self.assertEqual(router.running.list()[1].split()[1], "summary")
        await asyncio.gather(*tasks)
        self.assertEqual(sent, [("#c", ["summarized"])])

    async def test_drink_routes_as_running_async_command(self) -> None:
        async def fake_bluesky(send, target: str) -> None:
            await send(target, ["🤖 Bot is listening"])

        router = self.make_router(bluesky_runner=fake_bluesky)
        sent: list[tuple[str, list[str]]] = []

        async def send(target: str, lines: list[str]) -> None:
            sent.append((target, lines))

        await router.handle("alice", "#bluesky", "!drink", send)
        tasks = [info.task for info in router.running.tasks.values()]
        self.assertEqual(len(tasks), 1)
        self.assertIn("drink args=[]", router.running.list()[1])
        await asyncio.gather(*tasks)
        self.assertEqual(sent, [("#bluesky", ["🤖 Bot is listening"])])

    async def test_disabled_youtube_trigger_skips_youtube_preview(self) -> None:
        called: list[str] = []

        def fake_summary(text: str, fallback_url: str | None) -> list[str]:
            raise AssertionError("not used")

        router = self.make_router(summary_runner=fake_summary)

        async def send(target: str, lines: list[str]) -> None:
            called.extend(lines)

        await router.handle("alice", "#c", "!disable youtube", send)
        await router.handle("alice", "#c", "https://youtu.be/tq17_LlJCSo?t=655", send)
        self.assertEqual(called, ["Trigger youtube is now disabled"])
        self.assertFalse(router.running.list())

    async def test_zscore_routes_to_renderer(self) -> None:
        seen: list[str] = []

        def fake_zscore(text: str) -> list[str]:
            seen.append(text)
            return ["outlook unsure (p=45.24%) bits=280"]

        router = self.make_router(zscore_renderer=fake_zscore)
        sent: list[tuple[str, list[str]]] = []

        async def send(target: str, lines: list[str]) -> None:
            sent.append((target, lines))

        await router.handle("alice", "#c", "!zscore should i switch", send)
        self.assertEqual(seen, ["!zscore should i switch"])
        self.assertEqual(sent, [("#c", ["outlook unsure (p=45.24%) bits=280"])])

    async def test_twitter_routes_urls_and_llm_tool_run_to_renderer(self) -> None:
        seen: list[str] = []

        def fake_twitter(text: str) -> list[str]:
            seen.append(text)
            return ["DocumentingLibs @HistorianUSA1 May 06 2026", "💬 2453 ♻️ 323 ❤️ 2341"]

        router = self.make_router(twitter_renderer=fake_twitter)
        sent: list[tuple[str, list[str]]] = []

        async def send(target: str, lines: list[str]) -> None:
            sent.append((target, lines))

        await router.handle("alice", "#c", "https://x.com/HistorianUSA1/status/2052013873956352453", send)
        self.assertEqual(seen, ["https://x.com/HistorianUSA1/status/2052013873956352453"])
        self.assertEqual(sent, [("#c", ["DocumentingLibs @HistorianUSA1 May 06 2026", "💬 2453 ♻️ 323 ❤️ 2341"])])

        reply = router.run_llm_tool_command(
            LLMToolContext("#c", (), router.filters.state),
            "twitter",
            ["2052013873956352453"],
        )
        self.assertEqual(reply, ["DocumentingLibs @HistorianUSA1 May 06 2026", "💬 2453 ♻️ 323 ❤️ 2341"])
        self.assertEqual(seen[-1], "!twitter 2052013873956352453")

    async def test_nostr_routes_events_and_llm_tool_run_to_renderer(self) -> None:
        seen: list[str] = []

        def fake_nostr(text: str) -> list[str]:
            seen.append(text)
            return ["weev @weev Apr 19 2026", "RFK summoned to the Oval Office"]

        router = self.make_router(nostr_renderer=fake_nostr)
        sent: list[tuple[str, list[str]]] = []

        async def send(target: str, lines: list[str]) -> None:
            sent.append((target, lines))

        await router.handle("alice", "#c", "nostr:note1qqs9h777vva2rk9ek5jv0gm86fhgjp5rf0w2hvlaryz", send)
        self.assertEqual(seen, ["nostr:note1qqs9h777vva2rk9ek5jv0gm86fhgjp5rf0w2hvlaryz"])
        self.assertEqual(sent, [("#c", ["weev @weev Apr 19 2026", "RFK summoned to the Oval Office"])])

        reply = router.run_llm_tool_command(
            LLMToolContext("#c", (), router.filters.state),
            "nostr",
            ["note1qqs9h777vva2rk9ek5jv0gm86fhgjp5rf0w2hvlaryz"],
        )
        self.assertEqual(reply, ["weev @weev Apr 19 2026", "RFK summoned to the Oval Office"])
        self.assertEqual(seen[-1], "nostr:note1qqs9h777vva2rk9ek5jv0gm86fhgjp5rf0w2hvlaryz")

    async def test_ansi2irc_routes_urls_and_llm_tool_run_to_renderer(self) -> None:
        seen: list[str] = []

        def fake_ansi2irc(text: str) -> list[str]:
            seen.append(text)
            return ["ANSI→IRC (cp437 detected):", "░▒▓"]

        router = self.make_router(ansi2irc_renderer=fake_ansi2irc)
        sent: list[tuple[str, list[str]]] = []

        async def send(target: str, lines: list[str]) -> None:
            sent.append((target, lines))

        await router.handle("alice", "#c", "!ansi2irc https://example.test/a.ans", send)
        self.assertEqual(seen, ["!ansi2irc https://example.test/a.ans"])
        self.assertEqual(sent, [("#c", ["ANSI→IRC (cp437 detected):", "░▒▓"])])

        reply = router.run_llm_tool_command(
            LLMToolContext("#c", (), router.filters.state),
            "ansi2irc",
            ["https://example.test/a.ans"],
        )
        self.assertEqual(reply, ["ANSI→IRC (cp437 detected):", "░▒▓"])
        self.assertEqual(seen[-1], "!ansi2irc https://example.test/a.ans")

    async def test_echo_routes_to_renderer(self) -> None:
        seen: list[str] = []

        def fake_echo(text: str) -> list[str]:
            seen.append(text)
            return ["echoed"]

        router = self.make_router(echo_renderer=fake_echo)
        sent: list[tuple[str, list[str]]] = []

        async def send(target: str, lines: list[str]) -> None:
            sent.append((target, lines))

        await router.handle("alice", "#c", "!echo **test**", send)
        self.assertEqual(seen, ["!echo **test**"])
        self.assertEqual(sent, [("#c", ["echoed"])])

    async def test_reminders_alert_before_normal_message(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = JsonState(Path(tmp.name) / "state.json")
        current = datetime(2026, 2, 18, 23, 56, 30, tzinfo=timezone.utc)
        reminders = ReminderStore(state, now=lambda: current)
        reminders.handle("alice", "#c", "!remindme test in 1 second")
        current = datetime(2026, 2, 18, 23, 56, 32, tzinfo=timezone.utc)
        router = Router(
            vtrade=VTrade(state, prices=StaticPriceProvider({"TSLA": "250"})),
            filters=FilterStore(state),
            llm_client=None,
            default_model="openai/gpt-oss-120b",
            grok_model="x-ai/grok-4.1-fast",
            reminders=reminders,
        )
        sent: list[tuple[str, list[str]]] = []

        async def send(target: str, lines: list[str]) -> None:
            sent.append((target, lines))

        await router.handle("alice", "#c", "a", send)
        self.assertEqual(sent, [("#c", ["⏰ Reminder for alice: Test"])])

    async def test_disabled_reminders_hold_due_alerts_until_reenabled(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = JsonState(Path(tmp.name) / "state.json")
        current = datetime(2026, 2, 18, 23, 56, 30, tzinfo=timezone.utc)
        reminders = ReminderStore(state, now=lambda: current)
        reminders.handle("alice", "#c", "!remindme test in 1 second")
        router = Router(
            vtrade=VTrade(state, prices=StaticPriceProvider({"TSLA": "250"})),
            filters=FilterStore(state),
            llm_client=None,
            default_model="openai/gpt-oss-120b",
            grok_model="x-ai/grok-4.1-fast",
            reminders=reminders,
        )
        sent: list[tuple[str, list[str]]] = []

        async def send(target: str, lines: list[str]) -> None:
            sent.append((target, lines))

        await router.handle("alice", "#c", "!disable reminder", send)
        current = datetime(2026, 2, 18, 23, 56, 32, tzinfo=timezone.utc)
        await router.handle("alice", "#c", "a", send)
        await router.handle("alice", "#c", "!enable reminder", send)
        await router.handle("alice", "#c", "b", send)
        self.assertEqual(
            sent,
            [
                ("#c", ["Trigger reminder is now disabled"]),
                ("#c", ["Trigger reminder is now enabled"]),
                ("#c", ["⏰ Reminder for alice: Test"]),
            ],
        )


class StockRoutingTests(unittest.TestCase):
    def test_stock_command_routes_to_renderer(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = JsonState(Path(tmp.name) / "state.json")
        seen: list[str] = []

        def fake_stock(text: str) -> list[str]:
            seen.append(text)
            return ["stock chart"]

        router = Router(
            vtrade=VTrade(state, prices=StaticPriceProvider({"TSLA": "250"})),
            filters=FilterStore(state),
            llm_client=None,
            default_model="openai/gpt-oss-120b",
            grok_model="x-ai/grok-4.1-fast",
            ascii_art=AsciiArtStore.default(),
            stock_renderer=fake_stock,
        )
        self.assertEqual(router.handle_sync("alice", "!stock TSLA").lines, ["stock chart"])
        self.assertEqual(seen, ["!stock TSLA"])


if __name__ == "__main__":
    unittest.main()
