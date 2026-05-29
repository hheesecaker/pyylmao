from __future__ import annotations

import json
import tempfile
import unittest
import os
from pathlib import Path

from pyylmao.llm import CANCELLED_TOOL_RESULT, OpenRouterClient, SYSTEM_PROMPT
from pyylmao.history_store import record_history
from pyylmao.llm_tools import (
    LLMToolContext,
    LLMToolRegistry,
    WebSearchResult,
    infer_command_name_from_pattern,
    infer_pattern_from_code,
)
from pyylmao.state import JsonState
from pyylmao.tools_table import TOOL_INVENTORY, TOOLS


class LLMToolRegistryTests(unittest.TestCase):
    def make_registry(self) -> tuple[LLMToolRegistry, JsonState, tempfile.TemporaryDirectory[str]]:
        tmp = tempfile.TemporaryDirectory()
        state = JsonState(Path(tmp.name) / "state.json")
        registry = LLMToolRegistry(
            state,
            generated_dir=Path(tmp.name) / "generated",
            artifact_dir=Path(tmp.name) / "artifacts",
        )
        self.addCleanup(tmp.cleanup)
        return registry, state, tmp

    def test_read_command_reads_reconstructed_source(self) -> None:
        registry, _, _ = self.make_registry()
        text = registry.execute(LLMToolContext("#c", ()), "read_command", {"name": "kv"})
        self.assertIn("class KVStore", text)
        self.assertIn("def parse_kv_command", text)

    def test_read_command_accepts_logged_alias_names(self) -> None:
        registry, _, _ = self.make_registry()
        context = LLMToolContext("#c", ())

        self.assertIn("def render_ansi2irc_command", registry.execute(context, "read_command", {"name": "ansi2irc"}))
        self.assertIn("def render_ansi2irc_command", registry.execute(context, "read_command", {"name": "ansi2irc2"}))
        self.assertIn("class AsciiArtStore", registry.execute(context, "read_command", {"name": "ascii"}))
        self.assertIn("class BlueskyFeedWatcher", registry.execute(context, "read_command", {"name": "drink"}))
        self.assertIn("class ReminderStore", registry.execute(context, "read_command", {"name": "reminder"}))
        self.assertIn("def render_hf_command", registry.execute(context, "read_command", {"name": "hf"}))
        self.assertIn("def render_test_command", registry.execute(context, "read_command", {"name": "teste"}))
        self.assertIn("def render_urban_command", registry.execute(context, "read_command", {"name": "urban"}))
        self.assertIn("def render_stock_command", registry.execute(context, "read_command", {"name": "stock"}))
        self.assertIn("def render_fortune_command", registry.execute(context, "read_command", {"name": "fortune"}))
        self.assertIn("def render_cp_command", registry.execute(context, "read_command", {"name": "cp"}))
        self.assertIn("class WeatherRenderers", registry.execute(context, "read_command", {"name": "forecast"}))
        self.assertIn("def preview_title", registry.execute(context, "read_command", {"name": "link_title"}))
        self.assertIn("def parse_llm_prompt", registry.execute(context, "read_command", {"name": "gpt"}))
        self.assertIn("def parse_llm_prompt", registry.execute(context, "read_command", {"name": "convo"}))
        self.assertIn("def parse_llm_prompt", registry.execute(context, "read_command", {"name": "@@"}))
        self.assertIn("def render_eval_command", registry.execute(context, "read_command", {"name": "eval"}))
        self.assertIn("def kv_get", registry.execute(context, "read_command", {"name": "kv_get"}))
        self.assertIn("class KvContext", registry.execute(context, "read_command", {"name": "KvContext"}))
        self.assertIn("def md2irc", registry.execute(context, "read_command", {"name": "md2irc"}))
        self.assertIn("def render_invite_command", registry.execute(context, "read_command", {"name": "invite"}))
        self.assertIn("from pyylmao.ircbot import bot", registry.execute(context, "read_command", {"name": "invite"}))
        self.assertIn("def render_youtube_preview", registry.execute(context, "read_command", {"name": "youtube"}))
        self.assertIn("def run_summary_command", registry.execute(context, "read_command", {"name": "yt"}))
        self.assertIn("def random_command", registry.execute(context, "read_command", {"name": "random"}))
        self.assertIn('pattern = r"^\\.random\\s*(.*)$"', registry.execute(context, "read_command", {"name": "random"}))
        self.assertIn("def render_seen_command", registry.execute(context, "read_command", {"name": "seen"}))
        self.assertIn("from pyylmao.kv.backends.sqlite import default_root", registry.execute(context, "read_command", {"name": "seen"}))
        self.assertIn("def render_nostr_command", registry.execute(context, "read_command", {"name": "nostr"}))
        self.assertIn("def render_twitter_command", registry.execute(context, "read_command", {"name": "twitter"}))
        self.assertIn("def render_ytsearch_command", registry.execute(context, "read_command", {"name": "ytsearch"}))
        self.assertIn("class PollStore", registry.execute(context, "read_command", {"name": "poll"}))
        self.assertIn("def render_vote_command", registry.execute(context, "read_command", {"name": "vote"}))
        self.assertIn("def render_vote_command", registry.execute(context, "read_command", {"name": "votes"}))
        self.assertIn("def render_vote_command", registry.execute(context, "read_command", {"name": "poll_vote"}))
        self.assertIn("class TriviaStore", registry.execute(context, "read_command", {"name": "trivia"}))
        self.assertIn("class VocoderSynthesizer", registry.execute(context, "read_command", {"name": "vocoder"}))
        self.assertIn("def render_ligma_command", registry.execute(context, "read_command", {"name": "ligma"}))
        self.assertIn("class PhenoguessrStore", registry.execute(context, "read_command", {"name": "phenoguessr"}))
        self.assertIn("class PhenoguessrStore", registry.execute(context, "read_command", {"name": "pheno"}))
        pmall_source = registry.execute(context, "read_command", {"name": "pmall"})
        self.assertIn("class Tool(llm.Toolbox)", pmall_source)
        self.assertIn("def _onload", pmall_source)
        self.assertIn("channel_users", pmall_source)
        self.assertIn("connection.privmsg", pmall_source)
        self.assertIn("def channel_users", registry.execute(context, "read_command", {"name": "userlist"}))
        self.assertIn("def channel_users", registry.execute(context, "read_command", {"name": "names"}))
        self.assertIn("def channel_users", registry.execute(context, "read_command", {"name": "users"}))
        imgcap_source = registry.execute(context, "read_command", {"name": "imgcap"})
        self.assertIn('pattern = r"^(.*(https?://[^ ]+).*)$"', imgcap_source)
        self.assertIn("from pyylmao.kv import kv_delete, kv_get, kv_query, kv_set", imgcap_source)
        self.assertIn("llm.Attachment", imgcap_source)
        self.assertIn("No command found", registry.execute(context, "read_command", {"name": "cert"}))

    def test_write_command_and_revise_pattern_store_debug_artifacts(self) -> None:
        registry, state, tmp = self.make_registry()
        context = LLMToolContext("#c", ())
        result = registry.execute(
            context,
            "write_command",
            {"name": "new cmd", "code": "value = 'ok'\n", "pattern": r"^!new$"},
        )
        self.assertEqual(result, "No requirements found in provided code.")
        self.assertEqual((Path(tmp.name) / "generated" / "new_cmd.py").read_text(), "value = 'ok'\n")
        self.assertEqual(state.data["generated_commands"]["new_cmd"]["pattern"], r"^!new$")

        self.assertEqual(
            registry.execute(context, "revise_pattern", {"name": "new cmd", "pattern": r"^!new (.+)$"}),
            r"Pattern for new_cmd set to ^!new (.+)$",
        )
        self.assertEqual(state.data["generated_commands"]["new_cmd"]["pattern"], r"^!new (.+)$")

    def test_logged_digit_leading_generated_command_names_work(self) -> None:
        registry, state, tmp = self.make_registry()
        context = LLMToolContext("#c", ())
        code = "pattern = r'3daudio.html'\n"

        self.assertEqual(
            registry.execute(context, "write_command", {"name": "3daudio", "code": code}),
            "No requirements found in provided code.",
        )
        self.assertEqual((Path(tmp.name) / "generated" / "3daudio.py").read_text(), code)
        self.assertEqual(state.data["generated_commands"]["3daudio"]["pattern"], "3daudio.html")
        self.assertEqual(registry.execute(context, "read_command", {"name": "3daudio"}), code)
        self.assertEqual(
            registry.execute(context, "revise_pattern", {"name": "3daudio", "pattern": "3daudio.html"}),
            "Pattern for 3daudio set to 3daudio.html",
        )

    def test_write_command_reports_import_stdout_and_load_errors_like_logs(self) -> None:
        registry, state, tmp = self.make_registry()
        context = LLMToolContext("#c", ())

        self.assertEqual(
            registry.execute(
                context,
                "write_command",
                {
                    "name": "loader",
                    "pattern": r"^!loader$",
                    "code": "pattern = r'^!loader$'\nprint('loaded during import')\n",
                },
            ),
            "No requirements found in provided code.\nloaded during import",
        )
        self.assertEqual(
            registry.execute(
                context,
                "write_command",
                {
                    "name": "broken_loader",
                    "pattern": r"^!broken_loader$",
                    "code": "pattern = r'^!broken_loader$'\nraise ModuleNotFoundError(\"No module named 'pydub'\")\n",
                },
            ),
            "No requirements found in provided code.\n"
            "Skipping command broken_loader due to load error: ModuleNotFoundError(\"No module named 'pydub'\")",
        )

        broken_other = Path(tmp.name) / "generated" / "elliotsearch.py"
        broken_other.parent.mkdir(parents=True, exist_ok=True)
        broken_other.write_text("pattern = r'^!elliot$'\nimport pymupdf\n", encoding="utf-8")
        state.data["generated_commands"]["elliotsearch"] = {
            "path": str(broken_other),
            "pattern": r"^!elliot$",
        }

        self.assertEqual(
            registry.execute(
                context,
                "write_command",
                {
                    "name": "gay",
                    "pattern": r"^!gay (.+)$",
                    "code": "pattern = r'^!gay (.+)$'\ndef entrypoint(args, channel, nickname, username, hostname):\n    print(args[0])\n",
                },
            ),
            "No requirements found in provided code.\n"
            "Skipping command broken_loader due to load error: ModuleNotFoundError(\"No module named 'pydub'\")\n"
            "Skipping command elliotsearch due to load error: ModuleNotFoundError(\"No module named 'pymupdf'\")",
        )

    def test_write_command_infers_pattern_and_read_command_reads_generated_source(self) -> None:
        registry, state, tmp = self.make_registry()
        context = LLMToolContext("#c", ())
        code = "pattern = r'^!auto (.+)$'\ndef entrypoint(args, channel, nickname, username, hostname):\n    print(args[0])\n"
        result = registry.execute(
            context,
            "write_command",
            {"name": "auto", "code": code},
        )

        self.assertEqual(result, "No requirements found in provided code.")
        self.assertEqual(state.data["generated_commands"]["auto"]["pattern"], r"^!auto (.+)$")
        self.assertEqual(registry.execute(context, "read_command", {"name": "auto"}), code)
        self.assertEqual((Path(tmp.name) / "generated" / "auto.py").read_text(), code)

    def test_write_command_infers_missing_name_from_pattern(self) -> None:
        registry, state, tmp = self.make_registry()
        context = LLMToolContext("#c", ())
        code = "pattern = r'^!inspect2$'\ndef entrypoint(args, channel, nickname, username, hostname):\n    print('ok')\n"

        result = registry.execute(context, "write_command", {"code": code})

        self.assertEqual(result, "No requirements found in provided code.")
        self.assertEqual(state.data["generated_commands"]["inspect2"]["pattern"], r"^!inspect2$")
        self.assertEqual(registry.execute(context, "read_command", {"name": "inspect2"}), code)
        self.assertEqual((Path(tmp.name) / "generated" / "inspect2.py").read_text(), code)

    def test_write_command_prefers_code_when_content_is_description(self) -> None:
        registry, state, tmp = self.make_registry()
        context = LLMToolContext("#c", ())
        code = "def run(bot, channel, sender, args):\n    print('ok')\n"

        result = registry.execute(
            context,
            "write_command",
            {
                "name": "yolo",
                "pattern": r"^!yolo$",
                "code": code,
                "content": "Outputs a random number between 1 and 1,000,000",
            },
        )

        self.assertEqual(result, "No requirements found in provided code.")
        self.assertEqual((Path(tmp.name) / "generated" / "yolo.py").read_text(), code)
        self.assertEqual(state.data["generated_commands"]["yolo"]["description"], "Outputs a random number between 1 and 1,000,000")

    def test_command_tools_accept_logged_dot_py_command_names(self) -> None:
        registry, state, tmp = self.make_registry()
        context = LLMToolContext("#c", ())
        code = "pattern = r'^!ligma$'\ndef entrypoint(args, channel, nickname, username, hostname):\n    print('ok')\n"

        self.assertEqual(
            registry.execute(context, "write_command", {"name": "plugins/ligma.py", "code": code}),
            "No requirements found in provided code.",
        )
        self.assertEqual(registry.execute(context, "read_command", {"name": "ligma.py"}), code)
        self.assertIn("class KVStore", registry.execute(context, "read_command", {"name": "kv.py"}))
        self.assertEqual((Path(tmp.name) / "generated" / "ligma.py").read_text(), code)
        self.assertIn("ligma", state.data["generated_commands"])

    def test_run_tool_accepts_logged_generated_command_shape(self) -> None:
        registry, _, _ = self.make_registry()
        context = LLMToolContext("#c", ())
        code = "\n".join(
            [
                "pattern = r'^!auto (.+)$'",
                "def entrypoint(args, channel, nickname, username, hostname):",
                "    print(f'{nickname}@{channel}: {args[0]}')",
                "",
            ]
        )
        registry.execute(context, "write_command", {"name": "auto", "code": code})

        self.assertEqual(
            registry.execute(context, "run", {"cmd_name": "auto", "args": "['smoke']"}),
            "pyylmao@#c: smoke",
        )

    def test_run_tool_executes_logged_class_only_generated_command_api(self) -> None:
        registry, _, _ = self.make_registry()
        context = LLMToolContext("#c", ())
        code = "\n".join(
            [
                "import llm",
                "class Tool(llm.Toolbox):",
                "    pattern = r'^!classonly (.+)$'",
                "    def __init__(self, args, channel, connection):",
                "        self.args = args",
                "        self.channel = channel",
                "        self.connection = connection",
                "    def _onload(self):",
                "        print(f'{self.connection.get_nickname()}@{self.channel}: {self.args[0]}')",
                "",
            ]
        )
        registry.execute(context, "write_command", {"name": "classonly", "code": code})

        self.assertEqual(
            registry.execute(context, "run", {"cmd_name": "classonly", "args": "['smoke']"}),
            "pyylmao@#c: smoke",
        )

    def test_read_and_run_generated_file_without_state_entry(self) -> None:
        registry, state, tmp = self.make_registry()
        context = LLMToolContext("#c", ())
        generated_dir = Path(tmp.name) / "generated"
        generated_dir.mkdir()
        code = (
            "pattern = r'^!orphan (.+)$'\n"
            "def entrypoint(args, channel, nickname, username, hostname):\n"
            "    print(f'{nickname}@{channel}: {args[0]}')\n"
        )
        (generated_dir / "orphan.py").write_text(code, encoding="utf-8")

        self.assertNotIn("orphan", state.data.setdefault("generated_commands", {}))
        self.assertEqual(registry.execute(context, "read_command", {"name": "orphan"}), code)
        self.assertEqual(
            registry.execute(context, "run", {"cmd_name": "orphan", "args": "['smoke']"}),
            "pyylmao@#c: smoke",
        )

    def test_read_and_run_generated_package_directory_like_historical_commands(self) -> None:
        registry, state, tmp = self.make_registry()
        context = LLMToolContext("#c", ())
        package_dir = Path(tmp.name) / "generated" / "packaged"
        package_dir.mkdir(parents=True)
        code = (
            "pattern = r'^!packaged (.+)$'\n"
            "def entrypoint(args, channel, nickname, username, hostname):\n"
            "    print(f'{nickname}@{channel}: {args[0]}')\n"
        )
        (package_dir / "__init__.py").write_text(code, encoding="utf-8")
        state.data["generated_commands"] = {
            "packaged": {"path": str(package_dir), "pattern": r"^!packaged (.+)$"}
        }

        self.assertEqual(registry.execute(context, "read_command", {"name": "packaged"}), code)
        self.assertEqual(
            registry.execute(context, "run", {"cmd_name": "packaged", "args": "['smoke']"}),
            "pyylmao@#c: smoke",
        )

    def test_read_and_run_generated_package_directory_without_state_entry(self) -> None:
        registry, state, tmp = self.make_registry()
        context = LLMToolContext("#c", ())
        package_dir = Path(tmp.name) / "generated" / "orphanpkg"
        package_dir.mkdir(parents=True)
        code = (
            "pattern = r'^!orphanpkg (.+)$'\n"
            "def entrypoint(args, channel, nickname, username, hostname):\n"
            "    print(f'{nickname}@{channel}: {args[0]}')\n"
        )
        (package_dir / "__init__.py").write_text(code, encoding="utf-8")

        self.assertNotIn("orphanpkg", state.data.setdefault("generated_commands", {}))
        self.assertEqual(registry.execute(context, "read_command", {"name": "orphanpkg"}), code)
        self.assertEqual(
            registry.execute(context, "run", {"cmd_name": "orphanpkg", "args": "['smoke']"}),
            "pyylmao@#c: smoke",
        )

    def test_schemas_respect_tool_toggles(self) -> None:
        registry, state, _ = self.make_registry()
        state.data["llm_tool_enabled"] = {"run": False, "remember": True, "query_skills": True}
        names = {item["function"]["name"] for item in registry.schemas()}

        self.assertNotIn("run", names)
        self.assertIn("remember", names)
        self.assertIn("irc_command", names)
        self.assertIn("query_skills", names)

    def test_tool_schemas_explain_standard_generated_command_api(self) -> None:
        registry, _, _ = self.make_registry()
        schemas = {item["function"]["name"]: item["function"] for item in registry.schemas()}

        write_description = schemas["write_command"]["description"]
        self.assertIn("class Tool(llm.Toolbox)", write_description)
        self.assertIn("entrypoint(args, channel, nickname, username, hostname)", write_description)
        self.assertIn("name is optional", write_description)
        self.assertEqual(
            schemas["write_command"]["parameters"]["properties"]["code"]["description"],
            "Complete executable Python command module source.",
        )
        self.assertEqual(schemas["read_command"]["parameters"]["required"], [])
        self.assertEqual(schemas["write_command"]["parameters"]["required"], [])
        self.assertIn("Prefer cmd_name", schemas["run"]["description"])

    def test_all_tools_table_rows_have_schema_when_enabled(self) -> None:
        registry, state, _ = self.make_registry()
        for name, _, _ in TOOLS:
            state.data["llm_tool_enabled"] = {name: True}
            names = {item["function"]["name"] for item in registry.schemas()}
            self.assertIn(name, names)

    def test_all_generated_tool_inventory_rows_have_schema_when_enabled(self) -> None:
        registry, state, _ = self.make_registry()
        for name, _, _ in TOOL_INVENTORY:
            state.data["llm_tool_enabled"] = {name: True}
            names = {item["function"]["name"] for item in registry.schemas()}
            self.assertIn(name, names)

    def test_irc_command_records_raw_command_requests(self) -> None:
        registry, state, _ = self.make_registry()
        context = LLMToolContext("#c", ())

        self.assertEqual(
            registry.execute(context, "irc_command", {"command": "NAMES #c\nPRIVMSG #c : | "}),
            "queued IRC command: NAMES #c\nqueued IRC command: PRIVMSG #c : |",
        )
        self.assertEqual(
            state.data["irc_command_log"],
            [
                {"ts": state.data["irc_command_log"][0]["ts"], "target": "#c", "command": "NAMES #c"},
                {"ts": state.data["irc_command_log"][1]["ts"], "target": "#c", "command": "PRIVMSG #c : |"},
            ],
        )

    def test_irc_command_uses_live_sender_when_available(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = JsonState(Path(tmp.name) / "state.json")
        sent: list[str] = []

        def sender(commands: list[str]) -> str:
            sent.extend(commands)
            return "\n".join(f"sent IRC command: {command}" for command in commands)

        registry = LLMToolRegistry(state, raw_irc_sender=sender)
        context = LLMToolContext("#c", (), state)

        self.assertEqual(
            registry.execute(context, "irc_command", {"command": "NAMES #c\nWHO #c"}),
            "sent IRC command: NAMES #c\nsent IRC command: WHO #c",
        )
        self.assertEqual(sent, ["NAMES #c", "WHO #c"])
        self.assertEqual(
            [item["command"] for item in state.data["irc_command_log"]],
            ["NAMES #c", "WHO #c"],
        )

    def test_disabled_default_irc_and_builtin_tools_work_when_enabled(self) -> None:
        registry, state, _ = self.make_registry()
        state.data["kvstore"] = {
            "pyylmao": {
                "irc": {
                    "channels": {
                        "#c": {"users": {"bob": {}, "alice": {}}},
                        "#other": {"users": ["zoe"]},
                    }
                }
            }
        }
        context = LLMToolContext("#c", (), state)

        self.assertEqual(registry.execute(context, "channel_list", {}), "#c\n#other")
        self.assertEqual(registry.execute(context, "get_channel_users", {}), "bob\nalice")
        self.assertEqual(registry.execute(context, "get_channel_users", {"channel": "#other"}), "zoe")
        self.assertEqual(registry.execute(context, "llm_version", {}), "pyylmao llm tools v0.0.0")
        self.assertRegex(registry.execute(context, "llm_time", {}), r"^\d{4}-\d{2}-\d{2}T")
        self.assertIn("eval ok", registry.execute(context, "eval", {"code": "print('eval ok')"}))
        self.assertEqual(registry.execute(context, "eval", {}), "No code provided")

    def test_read_skill_exposes_logged_builtin_skills(self) -> None:
        registry, _, _ = self.make_registry()
        context = LLMToolContext("#c", ())

        self.assertIn("module-level `kv` helper", registry.execute(context, "read_skill", {"name": "KV"}))
        self.assertIn("module-level `kv` helper", registry.execute(context, "read_skill", {"name": "kvstore"}))
        self.assertIn("!img2irc <url>", registry.execute(context, "read_skill", {"name": "img2irc"}))
        self.assertIn("from pyylmao.helpers import img2irc", registry.execute(context, "read_skill", {"name": "img2irc"}))
        self.assertIn("historical image-rendering alias", registry.execute(context, "read_skill", {"name": "imghax"}))
        self.assertIn("!mdcat <file>", registry.execute(context, "read_skill", {"name": "md2irc"}))
        self.assertIn("md2irc(text).decode", registry.execute(context, "read_skill", {"name": "md2irc"}))
        self.assertIn("Generated command modules", registry.execute(context, "read_skill", {"name": "llm"}))
        self.assertIn("llm.get_model", registry.execute(context, "read_skill", {"name": "llm"}))

    def test_builtin_skills_are_listed_and_queryable(self) -> None:
        registry, _, _ = self.make_registry()
        context = LLMToolContext("#c", ())

        listed = registry.execute(context, "list_skills", {}).splitlines()
        self.assertIn("KV", listed)
        self.assertIn("img2irc", listed)
        self.assertIn("md2irc", listed)
        self.assertIn(
            "img2irc: Accepted forms include",
            registry.execute(context, "query_skills", {"query": "render ansi24"}),
        )

    def test_run_tool_keeps_shell_and_exec_debug_forms(self) -> None:
        registry, _, _ = self.make_registry()
        context = LLMToolContext("#c", ())

        self.assertIn(
            "shell smoke",
            registry.execute(context, "run", {"command": "printf 'shell smoke'"}),
        )
        self.assertIn(
            "exec smoke",
            registry.execute(context, "run", {"cmd_name": "exec", "args": '["print(\\"exec smoke\\")"]'}),
        )

    def test_run_tool_executes_saved_python_artifacts_like_logged_debug_flow(self) -> None:
        registry, _, _ = self.make_registry()
        context = LLMToolContext("#c", ())
        registry.execute(
            context,
            "save_artifact",
            {"filename": "debug_ansi.py", "contents": "print('artifact smoke')\n"},
        )

        self.assertIn(
            "artifact smoke",
            registry.execute(context, "run", {"cmd_name": "python3", "args": "['debug_ansi']"}),
        )
        self.assertIn(
            "artifact smoke",
            registry.execute(context, "run", {"cmd_name": "python", "args": "['/home/pyylmao/bot/debug_ansi.py']"}),
        )
        self.assertIn(
            "artifact smoke",
            registry.execute(context, "run", {"cmd_name": "exec", "args": "['debug_ansi.py']"}),
        )

    def test_run_tool_uses_reconstructed_command_runner_before_subprocess(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = JsonState(Path(tmp.name) / "state.json")
        calls = []

        def command_runner(context: LLMToolContext, cmd_name: str, args: list[str]) -> list[str] | None:
            calls.append((context.target, cmd_name, args))
            return [f"ran {cmd_name}: {','.join(args)}"]

        registry = LLMToolRegistry(state, command_runner=command_runner)

        self.assertEqual(
            registry.execute(LLMToolContext("#c", (), state), "run", {"cmd_name": "define", "args": "['gay']"}),
            "ran define: gay",
        )
        self.assertEqual(calls, [("#c", "define", ["gay"])])

    def test_reconstructed_commands_are_exposed_as_direct_llm_tools(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = JsonState(Path(tmp.name) / "state.json")
        calls = []

        def command_runner(context: LLMToolContext, cmd_name: str, args: list[str]) -> list[str] | None:
            calls.append((context.target, cmd_name, args))
            return [f"ran {cmd_name}: {','.join(args)}"]

        registry = LLMToolRegistry(state, command_runner=command_runner)
        schemas = {item["function"]["name"]: item["function"] for item in registry.schemas()}

        self.assertIn("define", schemas)
        self.assertIn("pyylmao command 'define'", schemas["define"]["description"])
        self.assertIn("args", schemas["define"]["parameters"]["properties"])
        self.assertEqual(
            registry.execute(LLMToolContext("#c", (), state), "define", {"args": "gay"}),
            "ran define: gay",
        )
        self.assertEqual(calls, [("#c", "define", ["gay"])])

    def test_disabled_commands_are_not_exposed_as_direct_llm_tools(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = JsonState(Path(tmp.name) / "state.json")
        state.data["trigger_enabled"] = {"define": False}
        registry = LLMToolRegistry(state, command_runner=lambda *_: ["unused"])

        names = {item["function"]["name"] for item in registry.schemas()}

        self.assertNotIn("define", names)

    def test_generated_commands_are_exposed_as_direct_llm_tools(self) -> None:
        registry, state, _ = self.make_registry()
        context = LLMToolContext("#c", (), state)
        code = (
            "pattern = r'^!auto (.+)$'\n"
            "def entrypoint(args, channel, nickname, username, hostname):\n"
            "    print(f'{nickname}@{channel}: {args[0]}')\n"
        )
        registry.execute(context, "write_command", {"name": "auto", "code": code})

        schemas = {item["function"]["name"]: item["function"] for item in registry.schemas()}

        self.assertIn("auto", schemas)
        self.assertIn("pyylmao command 'auto'", schemas["auto"]["description"])
        self.assertEqual(
            registry.execute(context, "auto", {"args": "smoke"}),
            "pyylmao@#c: smoke",
        )

    def test_read_command_without_name_lists_generated_and_builtin_commands(self) -> None:
        registry, _, _ = self.make_registry()
        context = LLMToolContext("#c", ())
        registry.execute(context, "write_command", {"name": "auto", "code": "pattern = r'^!auto$'\n"})

        text = registry.execute(context, "read_command", {})
        self.assertIn("Generated commands:", text)
        self.assertIn("- auto: ^!auto$", text)
        self.assertIn("Built-in commands:", text)
        self.assertIn("- kv: ^!kv", text)

    def test_save_and_read_artifact_match_logged_tool_shape(self) -> None:
        registry, state, tmp = self.make_registry()
        context = LLMToolContext("#c", ())
        old_base_url = os.environ.get("PYYLMAO_WWW_BASE_URL")
        os.environ["PYYLMAO_WWW_BASE_URL"] = "https://artifacts.example"
        self.addCleanup(self.restore_env, "PYYLMAO_WWW_BASE_URL", old_base_url)

        result = registry.execute(
            context,
            "save_artifact",
            {"filename": "web apps/demo.html", "contents": "<h1>ok</h1>\n", "create_dirs": "true"},
        )

        self.assertEqual(result, "━━☛ New artifact: https://artifacts.example/web%20apps/demo.html")
        self.assertEqual(
            (Path(tmp.name) / "artifacts" / "web apps" / "demo.html").read_text(),
            "<h1>ok</h1>\n",
        )
        self.assertEqual(
            registry.execute(context, "read_artifact", {"filename": "web apps/demo.html"}),
            "<h1>ok</h1>\n",
        )
        self.assertEqual(
            registry.execute(context, "read_artifact", {"filename": "attachment_0001"}),
            "Unable to access attachment. Please verifythe file or provide additional details.",
        )
        self.assertEqual(registry.execute(context, "read_artifact", {"filename": "missing"}), "Error: missing")
        self.assertEqual(registry.execute(context, "read_artifact", {"filename": "/etc/issue"}), "Error: issue")
        generated_package = Path(tmp.name) / "generated" / "spam"
        generated_package.mkdir(parents=True)
        generated_source = "pattern = r'^!spam$'\ndef entrypoint(args, channel, nickname, username, hostname):\n    print('spam')\n"
        (generated_package / "__init__.py").write_text(generated_source, encoding="utf-8")
        self.assertEqual(
            registry.execute(context, "read_artifact", {"filename": "commands/spam/__init__.py"}),
            generated_source,
        )
        self.assertEqual(
            registry.execute(context, "read_artifact", {"filename": "spam/__init__.py"}),
            generated_source,
        )
        state.data["generated_commands"]["spam"] = {"path": str(generated_package), "pattern": r"^!spam$"}
        self.assertEqual(
            registry.execute(context, "read_artifact", {"filename": "src/commands/spam/__init__.py"}),
            generated_source,
        )
        self.assertEqual(
            registry.execute(context, "save_artifact", {"filename": "../nope.txt", "contents": "bad"}),
            "Invalid artifact filename",
        )
        registry.execute(context, "save_artifact", {"filename": "root.txt", "contents": "root"})
        registry.execute(context, "save_artifact", {"filename": "web apps/second.txt", "contents": "second"})
        self.assertEqual(
            registry.execute(context, "list_artifacts", {}),
            "web apps/\nroot.txt",
        )
        self.assertEqual(
            registry.execute(context, "list_artifact", {}),
            "web apps/\nroot.txt",
        )
        self.assertEqual(
            registry.execute(context, "list_artifacts", {"subdir": "web apps"}),
            "web apps/demo.html\nweb apps/second.txt",
        )
        self.assertEqual(
            registry.execute(context, "list_artifacts", {"subdir": "../"}),
            "Invalid artifact directory",
        )

    def restore_env(self, name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def test_chat_history_skill_and_memory_tools(self) -> None:
        registry, _, _ = self.make_registry()
        context = LLMToolContext("#not-gay", (("alice", "one"), ("bob", "two")))
        self.assertEqual(
            registry.execute(context, "get_chat_history", {"max_lines": "1"}),
            "bob: two",
        )
        self.assertEqual(
            registry.execute(context, "create_skill", {"name": "KV", "content": "# KV\nkey-value store"}),
            "Done! Created the KV skill.",
        )
        self.assertEqual(registry.execute(context, "read_skill", {"name": "KV"}), "# KV\nkey-value store")
        self.assertEqual(registry.execute(context, "query_skills", {"query": "key-value"}), "KV: key-value store")
        self.assertEqual(
            registry.execute(context, "update_skill", {"name": "KV", "content": "# KV\nupdated"}),
            "Done! Updated the KV skill.",
        )
        self.assertEqual(registry.execute(context, "read_skill", {"name": "KV"}), "# KV\nupdated")
        self.assertEqual(
            registry.execute(context, "update_skill", {"name": "missing", "content": "nope"}),
            "No skill named missing",
        )
        self.assertEqual(registry.execute(context, "remember", {"text": "alice likes kv"}), "Remembered #1")
        self.assertEqual(
            registry.execute(context, "search_memories", {"queries": "kv"}),
            "#1: alice likes kv",
        )
        self.assertEqual(
            registry.execute(
                context,
                "remember",
                {"memories": '[{"key": "patois_mode", "value": "only talk to SuiEyedBoys in Jamaican patois"}]'},
            ),
            "Remembered #2",
        )
        self.assertEqual(
            registry.execute(context, "search_memories", {"queries": "patois.*jamaican"}),
            "#2: patois_mode: only talk to SuiEyedBoys in Jamaican patois",
        )
        registry.web_searcher = lambda query, profile: [
            WebSearchResult(
                "Jamaican Patois",
                "https://example.test/patois",
                f"{profile}: {query}",
            )
        ]
        self.assertEqual(
            registry.execute(
                context,
                "semantic_search",
                {"query": "jamaican", "phrases": "['patois']", "profile": "instant"},
            ),
            "Profile: instant\n"
            "Query: jamaican patois\n"
            "1. Jamaican Patois\n"
            "   URL: https://example.test/patois\n"
            "   instant: jamaican patois",
        )
        self.assertEqual(
            registry.execute(
                context,
                "semantic_search",
                {"query": "current bot news", "profile": "news"},
            ),
            "Profile: news\n"
            "Query: current bot news\n"
            "1. Jamaican Patois\n"
            "   URL: https://example.test/patois\n"
            "   news: current bot news",
        )
        self.assertEqual(
            registry.execute(
                context,
                "semantic_search",
                {"query": "tool search", "profile": "web_search"},
            ),
            "Profile: web_search\n"
            "Query: tool search\n"
            "1. Jamaican Patois\n"
            "   URL: https://example.test/patois\n"
            "   web_search: tool search",
        )
        self.assertEqual(
            registry.execute(context, "semantic_search", {}),
            "Profile: balanced\nNo search query provided.",
        )
        self.assertEqual(
            registry.execute(context, "search_memories", {"queries": "['.*']"}),
            "#1: alice likes kv\n#2: patois_mode: only talk to SuiEyedBoys in Jamaican patois",
        )
        self.assertEqual(
            registry.execute(context, "forget", {"keys": "['patois_mode']"}),
            "Forgot 1 memories",
        )
        self.assertEqual(
            registry.execute(context, "search_memories", {"queries": "patois"}),
            "No memories found.",
        )

    def test_chat_history_prefers_persisted_channel_history_and_can_include_bot(self) -> None:
        registry, state, _ = self.make_registry()
        record_history(state, "#not-gay", "alice", "one", ts=1)
        record_history(state, "#not-gay", "pyylmao", "bot line", role="assistant", model="test/model", ts=2)
        record_history(state, "#not-gay", "bob", "two", ts=3)
        context = LLMToolContext("#not-gay", (("fallback", "ignored"),), state)

        self.assertEqual(
            registry.execute(context, "get_chat_history", {"max_lines": "5"}),
            "alice: one\nbob: two",
        )
        self.assertEqual(
            registry.execute(context, "get_chat_history", {"max_lines": "2", "include_bot": "True"}),
            "pyylmao: bot line\nbob: two",
        )

    def test_openrouter_tool_loop_executes_and_traces_tools(self) -> None:
        payloads = []

        def transport(payload):
            payloads.append(payload)
            if len(payloads) == 1:
                return {
                    "model": "test/model",
                    "usage": {"prompt_tokens": 10, "completion_tokens": 2},
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "get_chat_history",
                                            "arguments": '{"max_lines":"1"}',
                                        },
                                    }
                                ],
                            }
                        }
                    ],
                }
            return {
                "model": "test/model",
                "usage": {"prompt_tokens": 12, "completion_tokens": 4},
                "choices": [{"message": {"role": "assistant", "content": "done"}}],
            }

        registry, _, _ = self.make_registry()
        tools = registry.bind(LLMToolContext("#c", (("alice", "hi"),)))
        client = OpenRouterClient("test-key", transport=transport)
        result = client.chat("read history", "test/model", tools=tools)

        self.assertEqual(result.lines, ["done"])
        self.assertEqual(result.prompt_tokens, 22)
        self.assertEqual(result.completion_tokens, 6)
        self.assertEqual(
            result.tool_traces,
            ("get_chat_history args: {'max_lines': '1'}", "read 1 lines after filter"),
        )
        self.assertIn("tools", payloads[0])
        self.assertIn("class Tool(llm.Toolbox)", payloads[0]["messages"][0]["content"])
        self.assertIn("def entrypoint(args, channel, nickname, username, hostname)", payloads[0]["messages"][0]["content"])
        self.assertEqual(payloads[1]["messages"][-1]["content"], "alice: hi")

    def test_openrouter_traces_persisted_history_reads_like_logs(self) -> None:
        payloads = []

        def transport(payload):
            payloads.append(payload)
            if len(payloads) == 1:
                return {
                    "model": "test/model",
                    "usage": {"prompt_tokens": 10, "completion_tokens": 2},
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "get_chat_history",
                                            "arguments": '{"channel":"#not-gay","max_lines":"2"}',
                                        },
                                    }
                                ],
                            }
                        }
                    ],
                }
            return {
                "model": "test/model",
                "usage": {"prompt_tokens": 12, "completion_tokens": 4},
                "choices": [{"message": {"role": "assistant", "content": "done"}}],
            }

        registry, state, _ = self.make_registry()
        record_history(state, "#not-gay", "alice", "one", ts=1)
        record_history(state, "#not-gay", "bob", "two", ts=2)
        tools = registry.bind(LLMToolContext("#not-gay", (("fallback", "ignored"),), state))
        client = OpenRouterClient("test-key", transport=transport)
        result = client.chat("read history", "test/model", tools=tools)

        self.assertEqual(result.lines, ["done"])
        self.assertEqual(
            result.tool_traces,
            (
                "get_chat_history args: {'channel': '#not-gay', 'max_lines': '2'}",
                "read 2 lines from chat history",
            ),
        )
        self.assertEqual(payloads[1]["messages"][-1]["content"], "alice: one\nbob: two")

    def test_system_prompt_documents_generated_command_api(self) -> None:
        self.assertIn("Put executable Python only in code", SYSTEM_PROMPT)
        self.assertIn("class Tool(llm.Toolbox)", SYSTEM_PROMPT)
        self.assertIn("def entrypoint(args, channel, nickname, username, hostname)", SYSTEM_PROMPT)
        self.assertIn("Use run with cmd_name and args", SYSTEM_PROMPT)

    def test_openrouter_default_tool_rounds_cover_logged_debug_depth(self) -> None:
        payloads = []

        def transport(payload):
            payloads.append(payload)
            if len(payloads) <= 10:
                return {
                    "model": "test/model",
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": f"call_{len(payloads)}",
                                        "type": "function",
                                        "function": {
                                            "name": "get_chat_history",
                                            "arguments": '{"max_lines":"1"}',
                                        },
                                    }
                                ],
                            }
                        }
                    ],
                }
            return {
                "model": "test/model",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                "choices": [{"message": {"role": "assistant", "content": "done"}}],
            }

        registry, _, _ = self.make_registry()
        tools = registry.bind(LLMToolContext("#c", (("alice", "hi"),)))
        client = OpenRouterClient("test-key", transport=transport)
        result = client.chat("debug a command", "test/model", tools=tools)

        self.assertEqual(result.lines, ["done"])
        self.assertEqual(result.request_count, 11)
        self.assertEqual(len(payloads), 11)

    def test_openrouter_chain_limit_uses_logged_message(self) -> None:
        payloads = []

        def transport(payload):
            payloads.append(payload)
            return {
                "model": "test/model",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": f"call_{len(payloads)}",
                                    "type": "function",
                                    "function": {
                                        "name": "get_chat_history",
                                        "arguments": '{"max_lines":"1"}',
                                    },
                                }
                            ],
                        }
                    }
                ],
            }

        registry, _, _ = self.make_registry()
        tools = registry.bind(LLMToolContext("#c", (("alice", "hi"),)))
        client = OpenRouterClient("test-key", transport=transport)
        result = client.chat("debug a command", "test/model", tools=tools, max_tool_rounds=2)

        self.assertEqual(result.lines, ["Chain limit of 2 exceeded."])
        self.assertEqual(result.request_count, 3)
        self.assertEqual(len(payloads), 3)

    def test_openrouter_tool_cancellation_suppresses_tool_execution_but_finishes_chat(self) -> None:
        payloads = []

        def transport(payload):
            payloads.append(payload)
            if len(payloads) == 1:
                return {
                    "model": "test/model",
                    "usage": {"prompt_tokens": 10, "completion_tokens": 2},
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "get_chat_history",
                                            "arguments": '{"max_lines":"1"}',
                                        },
                                    }
                                ],
                            }
                        }
                    ],
                }
            return {
                "model": "test/model",
                "usage": {"prompt_tokens": 20, "completion_tokens": 4},
                "choices": [{"message": {"role": "assistant", "content": "done without tools"}}],
            }

        registry, _, _ = self.make_registry()
        tools = registry.bind(LLMToolContext("#c", (("alice", "hi"),)))
        client = OpenRouterClient("test-key", transport=transport)
        result = client.chat("debug a command", "test/model", tools=tools, cancel_checker=lambda: True)

        self.assertEqual(result.lines, ["done without tools"])
        self.assertEqual(result.tool_traces, (CANCELLED_TOOL_RESULT,))
        self.assertEqual(result.request_count, 2)
        self.assertEqual(payloads[1]["messages"][-1]["role"], "tool")
        self.assertEqual(payloads[1]["messages"][-1]["content"], CANCELLED_TOOL_RESULT)

    def test_openrouter_max_time_cancellation_uses_logged_trace(self) -> None:
        payloads = []
        clock_values = [1000.0, 1601.25]

        def clock():
            if clock_values:
                return clock_values.pop(0)
            return 1601.25

        def transport(payload):
            payloads.append(payload)
            if len(payloads) == 1:
                return {
                    "model": "test/model",
                    "usage": {"prompt_tokens": 10, "completion_tokens": 2},
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "get_chat_history",
                                            "arguments": '{"max_lines":"1"}',
                                        },
                                    }
                                ],
                            }
                        }
                    ],
                }
            return {
                "model": "test/model",
                "usage": {"prompt_tokens": 20, "completion_tokens": 4},
                "choices": [{"message": {"role": "assistant", "content": "done after timeout"}}],
            }

        registry, _, _ = self.make_registry()
        tools = registry.bind(LLMToolContext("#c", (("alice", "hi"),)))
        client = OpenRouterClient("test-key", transport=transport, clock=clock)
        result = client.chat("debug a command", "test/model", tools=tools)

        self.assertEqual(result.lines, ["done after timeout"])
        self.assertEqual(
            result.tool_traces,
            (
                "max_time reached: 1601.25 1000 600",
                "Tool calls cancelled: max_time 600s reached",
            ),
        )
        self.assertEqual(payloads[1]["messages"][-1]["role"], "tool")
        self.assertEqual(payloads[1]["messages"][-1]["content"], "Tool calls cancelled: max_time 600s reached")

    def test_openrouter_tool_loop_traces_visible_debug_tool_results(self) -> None:
        payloads = []

        def transport(payload):
            payloads.append(payload)
            if len(payloads) == 1:
                return {
                    "model": "test/model",
                    "usage": {"prompt_tokens": 10, "completion_tokens": 2},
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "write_command",
                                            "arguments": json.dumps(
                                                {
                                                    "name": "smoke",
                                                    "pattern": "^!smoke$",
                                                    "code": "pattern = r'^!smoke$'\n",
                                                }
                                            ),
                                        },
                                    }
                                ],
                            }
                        }
                    ],
                }
            return {
                "model": "test/model",
                "usage": {"prompt_tokens": 12, "completion_tokens": 4},
                "choices": [{"message": {"role": "assistant", "content": "done"}}],
            }

        registry, _, _ = self.make_registry()
        tools = registry.bind(LLMToolContext("#c", ()))
        client = OpenRouterClient("test-key", transport=transport)
        result = client.chat("write a command", "test/model", tools=tools)

        self.assertEqual(result.lines, ["done"])
        self.assertEqual(result.tool_traces[0], "write_command args: {'name': 'smoke', 'pattern': '^!smoke$', 'code': \"pattern = r'^!smoke$' | \"}")
        self.assertEqual(result.tool_traces[1], "No requirements found in provided code.")
        self.assertEqual(payloads[1]["messages"][-1]["content"], "No requirements found in provided code.")


class PatternInferenceTests(unittest.TestCase):
    def test_infers_ast_and_regex_pattern_assignments(self) -> None:
        self.assertEqual(infer_pattern_from_code("pattern = r'^!x (.+)$'\n"), r"^!x (.+)$")
        self.assertEqual(infer_pattern_from_code('pattern = "^!x$"\n'), r"^!x$")
        self.assertEqual(
            infer_pattern_from_code("import llm\nclass X(llm.Toolbox):\n    pattern = r'^!class$'\n"),
            r"^!class$",
        )
        self.assertEqual(infer_pattern_from_code("print('x')\n"), "")

    def test_infers_command_name_from_common_regex_triggers(self) -> None:
        self.assertEqual(infer_command_name_from_pattern(r"^!inspect2$"), "inspect2")
        self.assertEqual(infer_command_name_from_pattern(r"^\.random\s*(.*)$"), "random")
        self.assertEqual(infer_command_name_from_pattern(r"^([!?])livebench(?:\s+(.*))?$"), "livebench")
        self.assertEqual(infer_command_name_from_pattern(r"^!(?:np|play|queue)\s?(.*)$"), "np")
        self.assertEqual(infer_command_name_from_pattern(r"(?:youtu\.?be)"), "")


if __name__ == "__main__":
    unittest.main()
