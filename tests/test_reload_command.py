from __future__ import annotations

import unittest

from pyylmao.reload_command import LLM_RELOAD_MODULES, is_reload_command, render_reload_command


class ReloadCommandTests(unittest.TestCase):
    def test_detects_reload_commands(self) -> None:
        self.assertTrue(is_reload_command("!reload"))
        self.assertTrue(is_reload_command("!reload md2irc"))
        self.assertTrue(is_reload_command("!rehash"))
        self.assertFalse(is_reload_command("!reloadx md2irc"))

    def test_bare_reload_matches_logged_empty_response(self) -> None:
        self.assertEqual(render_reload_command("!reload"), ["no handler modules found"])

    def test_rehash_matches_logged_config_reload(self) -> None:
        self.assertEqual(render_reload_command("!rehash"), ["Configuration reloaded successfully"])

    def test_known_module_mappings_match_logs(self) -> None:
        self.assertEqual(
            render_reload_command("!reload md2irc"),
            ["reloaded:", "- pyylmao.helpers.md2irc"],
        )
        self.assertEqual(
            render_reload_command("!reload gpt.common"),
            ["reloaded:", "- pyylmao.commands.gpt.common"],
        )
        self.assertEqual(
            render_reload_command("!reload helpers.img2irc"),
            ["reloaded:", "- pyylmao.helpers.img2irc"],
        )
        self.assertEqual(
            render_reload_command("!reload handlers.kvstore"),
            ["reloaded:", "- pyylmao.handlers.kvstore"],
        )
        self.assertEqual(
            render_reload_command("!reload handlers.reload"),
            ["reloaded:", "- pyylmao.handlers.reload"],
        )
        self.assertEqual(
            render_reload_command("!reload anagram_rs"),
            ["reloaded:", "- anagram_rs", "- anagram_rs.anagram_rs"],
        )
        self.assertEqual(
            render_reload_command("!reload backends.sqlite"),
            ["reloaded:", "- pyylmao.kv.backends.sqlite"],
        )
        self.assertEqual(
            render_reload_command("!reload pyylmao.kv.backends.sqlite"),
            ["reloaded:", "- pyylmao.kv.backends.sqlite"],
        )
        self.assertEqual(
            render_reload_command("!reload pyylmao.config"),
            ["reloaded:", "- pyylmao.config"],
        )
        self.assertEqual(
            render_reload_command("!reload mdbuffer"),
            ["reloaded:", "- pyylmao.commands.gpt.mdbuffer"],
        )

    def test_kvstore_reload_matches_logged_loaded_modules(self) -> None:
        self.assertEqual(
            render_reload_command("!reload kvstore"),
            [
                "reloaded:",
                "- llama_index.core.storage.kvstore",
                "- llama_index.core.storage.kvstore.simple_kvstore",
                "- llama_index.core.storage.kvstore.types",
                "- pyylmao.handlers.kvstore",
            ],
        )

    def test_llm_reload_matches_logged_loaded_modules(self) -> None:
        self.assertEqual(
            render_reload_command("!reload llm"),
            ["reloaded:"] + [f"- {name}" for name in LLM_RELOAD_MODULES],
        )

    def test_logged_no_match_reload_cases(self) -> None:
        self.assertEqual(render_reload_command("!reload gpt.billingD"), ["no modules found matching query"])
        self.assertEqual(render_reload_command("!reload helpres.img2irc"), ["no modules found matching query"])
        self.assertEqual(render_reload_command("!reload handlers.reloadd"), ["no modules found matching query"])
        self.assertEqual(render_reload_command("!reload unknown"), ["no modules found matching query"])

    def test_logged_failed_reload_cases(self) -> None:
        self.assertEqual(
            render_reload_command("!reload commands.urbandict"),
            ["failed:", "- pyylmao.commands.urbandict: parent 'pyylmao.commands' not in sys.modules"],
        )
        self.assertEqual(
            render_reload_command("!reload img2irc"),
            [
                "reloaded:",
                "- pyylmao.helpers.img2irc",
                "failed:",
                "- pyylmao.commands.img2irc: parent 'pyylmao.commands' not in sys.modules",
                "- pyylmao.commands.img2irc2: parent 'pyylmao.commands' not in sys.modules",
            ],
        )

    def test_handlers_help_error_matches_logged_error(self) -> None:
        self.assertEqual(
            render_reload_command("!reload handlers.help"),
            ['Error: TypeError("reload_handlers() got an unexpected keyword argument \'dryrun\'")'],
        )


if __name__ == "__main__":
    unittest.main()
