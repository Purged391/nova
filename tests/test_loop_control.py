"""Test loop control parsing, execution, and function boundaries."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
import sys
import unittest

import ast_nodes as ast
from interpreter import Interpreter, NovaRuntimeError, run
from lexer import Lexer, TokenKind as K
from parser import parse, ParseError


def source(body):
    return 'func main:\n    run:\n' + '\n'.join('        ' + line for line in body.splitlines())


class LoopControlTests(unittest.TestCase):
    def test_keywords(self):
        self.assertEqual([t.kind for t in Lexer('break continue breaker continued').tokenize()][:4],
                         [K.BREAK, K.CONTINUE, K.IDENTIFIER, K.IDENTIFIER])

    def test_ast_positions(self):
        statements = parse(source('while true:\n    break\n    continue')).functions[0].run_block.statements[0].block.statements
        self.assertIsInstance(statements[0], ast.BreakStmt)
        self.assertIsInstance(statements[1], ast.ContinueStmt)
        self.assertEqual(statements[0].source_span, ast.SourceSpan(4, 13, 4, 18))
        self.assertEqual(statements[1].to_dict()['type'], 'ContinueStmt')

    def test_outside_loop_even_unreachable(self):
        for keyword in ('break', 'continue'):
            for body in (keyword, 'if false:\n    ' + keyword,
                         'while false:\n    print()\n' + keyword):
                with self.subTest(body=body), self.assertRaisesRegex(ParseError, 'only allowed inside a loop'):
                    parse(source(body))
            with self.assertRaises(ParseError):
                parse(source('while true:\n    break') + '\nfunc other:\n    run:\n        ' + keyword)

    def test_no_arguments(self):
        for keyword in ('break', 'continue'):
            with self.assertRaises(ParseError):
                parse(source('while true:\n    ' + keyword + ' 1'))

    def test_break_skips_rest_and_continues_after_loop(self):
        self.assertEqual(run(source('let x = 0\nwhile true:\n    x = 1\n    break\n    x = 2\nreturn x')), 1)

    def test_continue_rechecks_condition_and_scope(self):
        text = source('let x = 0\nlet total = 0\nwhile x < 4:\n    let local = x\n    x = x + 1\n    if x == 2:\n        continue\n    total = total + x\nreturn total')
        self.assertEqual(run(text), 8)

    def test_nested_loops_nearest_target(self):
        text = source('let x = 0\nlet total = 0\nwhile x < 3:\n    x = x + 1\n    let y = 0\n    while y < 5:\n        y = y + 1\n        if y == 1:\n            continue\n        total = total + 1\n        break\n    total = total + 10\nreturn total')
        self.assertEqual(run(text), 33)

    def test_return_still_exits_function(self):
        self.assertEqual(run(source('while true:\n    if true:\n        return 7\n    break\nreturn 8')), 7)

    def test_manual_ast_cannot_control_callers_loop(self):
        for node_class in (ast.BreakStmt, ast.ContinueStmt):
            program = parse('func helper:\n    run:\n        return 1\n' + source('while true:\n    helper()\n    break\nreturn 2'))
            program.functions[0].run_block.statements = [node_class()]
            runtime = Interpreter(program)
            with self.assertRaisesRegex(NovaRuntimeError, 'cannot leave a function'):
                runtime.call('main')

    def test_cli(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, str(root / 'nova.py'), str(root / 'examples/loop_control.nova')],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '1\n2\n4\n5\n6\nDone\n')


if __name__ == '__main__':
    unittest.main()
