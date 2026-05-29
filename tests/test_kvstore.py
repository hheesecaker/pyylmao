from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyylmao.kvstore import KVStore, is_kv_command, parse_value
from pyylmao.state import JsonState


class KVStoreTests(unittest.TestCase):
    def make_store(self) -> KVStore:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return KVStore(JsonState(Path(tmp.name) / "state.json"))

    def test_detects_kv_commands(self) -> None:
        self.assertTrue(is_kv_command("!kv get md2irc.options.use_figlet"))
        self.assertTrue(is_kv_command("!kv set commands.trivia {}"))
        self.assertFalse(is_kv_command("!kval get x"))

    def test_get_default_scalar_matches_logs(self) -> None:
        store = self.make_store()
        self.assertEqual(store.handle("!kv get md2irc.options.use_figlet"), ["True"])

    def test_set_and_get_scalar(self) -> None:
        store = self.make_store()
        self.assertEqual(
            store.handle("!kv set md2irc.options.use_figlet False"),
            ["Set md2irc.options.use_figlet to:", "root", "└── value: false"],
        )
        self.assertEqual(store.handle("!kv get md2irc.options.use_figlet"), ["False"])

    def test_get_missing_path(self) -> None:
        store = self.make_store()
        self.assertEqual(store.handle("!kv get .commands.gpt._default.system.10"), [".commands.gpt._default.system.10 is not set"])

    def test_query_length(self) -> None:
        store = self.make_store()
        self.assertEqual(
            store.handle("!kv query .commands.gpt._default.system|length"),
            ["root", "└── value: 9"],
        )

    def test_tree_render_for_list(self) -> None:
        store = self.make_store()
        lines = store.handle("!kv get commands.gpt._default.system")
        assert lines is not None
        self.assertEqual(lines[0], "root")
        self.assertIn('├── [0]: "Be concise, answer simple questions with simple answer"', lines)
        self.assertIn('"DO NOT prepend your message with your nickname in pointy brackets"', lines[-1])

    def test_parse_json_like_values(self) -> None:
        self.assertEqual(parse_value("{}"), {})
        self.assertEqual(parse_value("False"), False)
        self.assertEqual(parse_value('{"reasoning": {"enabled": False}}'), '{"reasoning": {"enabled": False}}')
        self.assertEqual(parse_value('{"twitPic": true}'), {"twitPic": True})
        self.assertEqual(parse_value("123"), 123)
        self.assertEqual(parse_value("plain text"), "plain text")

    def test_append_creates_and_extends_lists(self) -> None:
        store = self.make_store()
        self.assertEqual(store.handle("!kv append bla a"), ["None"])
        self.assertEqual(store.handle("!kv append bla b"), ["None"])
        self.assertEqual(store.handle("!kv get bla"), ["root", '├── [0]: "a"', '└── [1]: "b"'])

    def test_tree_render_matches_newer_logged_style(self) -> None:
        store = self.make_store()
        store.handle('!kv set commands.twitter {"enabled": true, "ansi": {"fix": true}}')
        self.assertEqual(
            store.handle("!kv get commands.twitter"),
            [
                "root",
                "├── ansi",
                "│  └── fix: true",
                "└── enabled: true",
            ],
        )

    def test_delete_removes_paths(self) -> None:
        store = self.make_store()
        store.handle("!kv set commands.gpt.grok.options.reasoning_enabled false")
        self.assertEqual(
            store.handle("!kv del commands.gpt.grok.options.reasoning_enabled"),
            ["Deleted commands.gpt.grok.options.reasoning_enabled"],
        )
        self.assertEqual(
            store.handle("!kv get commands.gpt.grok.options.reasoning_enabled"),
            ["commands.gpt.grok.options.reasoning_enabled is not set"],
        )

    def test_unsupported_actions_match_logged_unknown_error_shape(self) -> None:
        store = self.make_store()
        self.assertEqual(
            store.handle("!kv update man my"),
            ["unknown error, op=update args=['update', 'man', 'my']"],
        )
        self.assertEqual(
            store.handle("!kv delete man"),
            ["unknown error, op=delete args=['delete', 'man', '']"],
        )

    def test_query_keys_and_bracket_indexes(self) -> None:
        store = self.make_store()
        store.handle('!kv set pyylmao.irc.channels."#not-gay".history []')
        store.handle('!kv append pyylmao.irc.channels."#not-gay".history {"message":"hi"}')
        self.assertEqual(
            store.handle('!kv query pyylmao|keys'),
            ["Query returned no results"],
        )
        self.assertEqual(
            store.handle('!kv query .pyylmao.irc.channels."#not-gay"|keys'),
            ["root", '└── [0]: "history"'],
        )
        self.assertEqual(
            store.handle('!kv query .pyylmao.irc.channels."#not-gay".history|length'),
            ["root", "└── value: 1"],
        )
        self.assertEqual(
            store.handle('!kv query .pyylmao.irc.channels."#not-gay".history[0]'),
            ["root", '└── message: "hi"'],
        )

    def test_query_keys_on_missing_or_null_path_matches_logged_jq_error(self) -> None:
        store = self.make_store()
        self.assertEqual(
            store.handle("!kv query .cfg|keys"),
            ["query error: ValueError('null (null) has no keys')"],
        )
        self.assertEqual(
            store.handle("!kv query .commands.phenoguesser|keys"),
            ["query error: ValueError('null (null) has no keys')"],
        )
        store.handle("!kv set nullish null")
        self.assertEqual(
            store.handle("!kv query .nullish|keys"),
            ["query error: ValueError('null (null) has no keys')"],
        )

    def test_query_logged_jq_compile_errors_for_unquoted_keys(self) -> None:
        store = self.make_store()
        self.assertEqual(
            store.handle("!kv query .commands.trivia.state._not-gay|keys"),
            [
                "query error: ValueError('jq: error: gay/0 is not defined at <top-level>, line 1, column 29:\\n"
                "    .commands.trivia.state._not-gay|keys \\n"
                "                                ^^^\\n"
                "jq: 1 compile error')"
            ],
        )
        self.assertEqual(
            store.handle("!kv query .pyylmao.irc.channels.#superbowl.history|length"),
            [
                'query error: ValueError("jq: error: syntax error, unexpected end of file, expecting FORMAT or QQSTRING_START or '
                "'[' at <top-level>, line 1, column 47:\\n"
                "    .pyylmao.irc.channels.#superbowl.history|length\\n"
                "                                                  ^\\n"
                'jq: 1 compile error")'
            ],
        )
        self.assertEqual(
            store.handle("!kv query .pyylmao.irc.channels.'#superbowl'.history|length"),
            [
                'query error: ValueError("jq: error: syntax error, unexpected INVALID_CHARACTER, expecting FORMAT or QQSTRING_START or '
                "'[' at <top-level>, line 1, column 23:\\n"
                "    .pyylmao.irc.channels.'#superbowl'.history|length\\n"
                "                          ^\\n"
                'jq: 1 compile error")'
            ],
        )
        self.assertEqual(
            store.handle("!kv query .pyylmao.irc.channels['#superbowl'].history|length"),
            [
                'query error: ValueError("jq: error: syntax error, unexpected INVALID_CHARACTER at <top-level>, line 1, column 23:\\n'
                "    .pyylmao.irc.channels['#superbowl'].history|length\\n"
                "                          ^\\n"
                'jq: 1 compile error")'
            ],
        )

    def test_query_list_slices_match_logged_jq_shape(self) -> None:
        store = self.make_store()
        self.assertEqual(
            store.handle("!kv query .commands.gpt._default.system[-2:]"),
            [
                "root",
                '├── [0]: "Do not include IRC nickname tags in your response"',
                '└── [1]: "DO NOT prepend your message with your nickname in pointy brackets"',
            ],
        )
        error = store.handle("!kv query .commands.gpt._default.system.[-2:]")
        assert error is not None
        self.assertEqual(len(error), 1)
        self.assertTrue(error[0].startswith("query error: ValueError("))
        self.assertIn(".commands.gpt._default.system.[-2:]", error[0])

    def test_query_string_literals_match_logged_jq_shape(self) -> None:
        store = self.make_store()
        self.assertEqual(store.handle('!kv query "ok"'), ["root", '└── value: "ok"'])
        self.assertEqual(store.handle('!kv query "im gay"'), ["root", '└── value: "im gay"'])
        self.assertEqual(store.handle("!kv query 123"), ["root", "└── value: 123"])
        self.assertEqual(store.handle("!kv query pyylmao|keys"), ["Query returned no results"])

    def test_query_to_entries_renders_logged_root_entries(self) -> None:
        store = self.make_store()
        store.handle("!kv set alpha [1,2]")
        lines = store.handle('!kv query to_entries[] | select(.value | type == "array" and length > 100) | .key')
        assert lines is not None
        self.assertEqual(lines[0], "root")
        self.assertIn('│  ├── key: "commands"', lines)
        self.assertIn('   ├── key: "alpha"', lines)
        self.assertIn("      ├── [0]: 1", lines)
        self.assertIn("      └── [1]: 2", lines)

    def test_get_json_and_raw_flags(self) -> None:
        store = self.make_store()
        store.handle('!kv set commands.urban {"enabled": true}')
        self.assertEqual(store.handle("!kv get +json commands.urban"), ['{', '  "enabled": true', '}'])
        self.assertEqual(store.handle("!kv +raw get commands.urban"), ["{'enabled': True}"])
        self.assertEqual(
            store.handle("!kv json commands.urban"),
            ["unknown error, op=json args=['json', 'commands.urban', '']"],
        )
        self.assertEqual(store.handle("!kv raw commands.urban"), ["{'enabled': True}"])

    def test_stats_flag_renders_new_values_for_mutations(self) -> None:
        store = self.make_store()
        self.assertEqual(
            store.handle("!kv set a.b c +stats"),
            ["Set a.b to:", "root", '└── value: "c"'],
        )
        self.assertEqual(
            store.handle("!kv +stats set a.b d"),
            ["Set a.b to:", "root", '└── value: "d"'],
        )
        self.assertEqual(
            store.handle("!kv set a.b [] +stats"),
            ["Set a.b to:", "root"],
        )
        self.assertEqual(
            store.handle("!kv append a.b ok +stats"),
            ["Appended to a.b. New value:", "root", '└── [0]: "ok"'],
        )
        self.assertEqual(
            store.handle("!kv append a.b aa +stats"),
            ["Appended to a.b. New value:", "root", '├── [0]: "ok"', '└── [1]: "aa"'],
        )

    def test_info_and_modes(self) -> None:
        store = self.make_store()
        info = store.handle("!kv info")
        assert info is not None
        self.assertEqual(info[0], "Backend: sqlite v0.0.0")
        self.assertTrue(info[1].startswith("Database: "))
        self.assertEqual(store.handle("!kv modes"), ["Modes: get, set, query, append, del, info"])


if __name__ == "__main__":
    unittest.main()
