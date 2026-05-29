from __future__ import annotations

import unittest

from pyylmao.eval_command import (
    is_eval_command,
    render_eval_command,
    reset_eval_builtins_for_tests,
)


class EvalCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_eval_builtins_for_tests()

    def test_simple_expression_and_newline_string_match_logs(self) -> None:
        self.assertTrue(is_eval_command('eval "hello"'))
        self.assertEqual(render_eval_command('eval "hello"', "#bowlcut", "pizza2"), ["hello"])
        self.assertEqual(render_eval_command(r'eval "\r\nQUIT :bye"', "#bowlcut", "pizza2"), ["QUIT :bye"])

    def test_generated_command_namespace_shape(self) -> None:
        self.assertEqual(render_eval_command("eval args", "#bowlcut", "pizza2"), ["['args']"])
        self.assertEqual(
            render_eval_command("eval list(globals().keys())", "#bowlcut", "pizza2"),
            [
                "['__name__', '__file__', '__package__', '__builtins__', "
                "'channel', 'nickname', 'username', 'hostname', 'args', "
                "'pattern', 'entrypoint']"
            ],
        )

    def test_errors_and_stdout_are_rendered_like_generated_command_output(self) -> None:
        self.assertEqual(render_eval_command("eval 1+2+3", "#bowlcut", "pizza2"), ["6"])
        self.assertEqual(render_eval_command('eval print("hello")', "#bowlcut", "pizza2"), ["hello", "None"])
        self.assertEqual(
            render_eval_command('eval globals()["os"]=__import__("os")', "#bowlcut", "pizza2"),
            ["Eval error: invalid syntax (<string>, line 1)"],
        )

    def test_unanchored_regex_matches_later_eval_word(self) -> None:
        self.assertEqual(
            render_eval_command(
                "grok doesn't like writing commands that only match at the beginning of a line eval 1+2+3",
                "#bowlcut",
                "pizza2",
            ),
            ["6"],
        )
        self.assertEqual(
            render_eval_command("yeah no statements inside eval sadly", "#bowlcut", "pizza2"),
            ["Eval error: name 'sadly' is not defined"],
        )

    def test_globals_do_not_persist_but_builtins_do(self) -> None:
        self.assertEqual(
            render_eval_command('eval globals().__setitem__("os",__import__("os"))', "#bowlcut", "pizza2"),
            ["None"],
        )
        self.assertEqual(
            render_eval_command("eval os", "#bowlcut", "pizza2"),
            ["Eval error: name 'os' is not defined"],
        )

        self.assertEqual(
            render_eval_command('eval __builtins__.__setitem__("foo","bar")', "#bowlcut", "pizza2"),
            ["None"],
        )
        self.assertEqual(render_eval_command("eval foo", "#bowlcut", "pizza2"), ["bar"])


if __name__ == "__main__":
    unittest.main()
