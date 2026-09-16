"""Verify while parsing, execution, scope, and CLI behavior."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
import sys
import unittest

import ast_nodes as ast
from interpreter import NovaRuntimeError, run
from lexer import Lexer, TokenKind as K
from parser import parse, ParseError


def source(body):
    return 'func main:\n    run:\n' + '\n'.join('        ' + line for line in body.splitlines())


class WhileTests(unittest.TestCase):
    def test_keyword(self):
        tokens = Lexer('while while_count').tokenize()
        self.assertEqual([t.kind for t in tokens[:2]], [K.WHILE, K.IDENTIFIER])

    def test_ast_and_span(self):
        node = parse(source('while false:\n    return 1')).functions[0].run_block.statements[0]
        self.assertIsInstance(node, ast.WhileStmt)
        self.assertEqual(node.source_span, ast.SourceSpan(3, 9, 4, 21))
        self.assertEqual(node.to_dict()['type'], 'WhileStmt')
        self.assertIs(node.condition.value, False)

    def test_iteration_and_fresh_scope(self):
        self.assertEqual(run(source('let x = 0\nwhile x < 3:\n    let next = x + 1\n    x = next\nreturn x')), 3)

    def test_false_skips_body(self):
        self.assertEqual(run(source('while false:\n    return missing\nreturn 4')), 4)

    def test_nested_loops_and_return(self):
        self.assertEqual(run(source('let x = 0\nlet total = 0\nwhile x < 2:\n    let y = 0\n    while y < 3:\n        total = total + 1\n        y = y + 1\n    x = x + 1\nreturn total')), 6)
        self.assertEqual(run(source('while true:\n    while true:\n        return 7\nreturn 1 / 0')), 7)

    def test_local_does_not_escape(self):
        with self.assertRaisesRegex(NovaRuntimeError, 'Undefined variable'):
            run(source('let x = 0\nwhile x < 1:\n    let local = 1\n    x = x + 1\nreturn local'))

    def test_condition_call_runs_each_time(self):
        function = 'func check:\n    inputs n: number\n    run:\n        print(n)\n        return n < 2\n'
        output = StringIO()
        with redirect_stdout(output):
            run(function + source('let x = 0\nwhile check(x):\n    x = x + 1'))
        self.assertEqual(output.getvalue(), '0\n1\n2\n')

    def test_boolean_required(self):
        with self.assertRaisesRegex(NovaRuntimeError, 'Expected bool') as caught:
            run(source('while 1:\n    return 0'))
        self.assertEqual((caught.exception.line, caught.exception.column), (3, 15))

    def test_invalid_syntax(self):
        for body in ['while:\n    return 1', 'while true\n    return 1',
                     'while true:', 'while false:\n    return 1\nelse:\n    return 2']:
            with self.subTest(body=body), self.assertRaises(ParseError):
                parse(source(body))

    def test_cli(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, str(root / 'nova.py'), str(root / 'examples' / 'while_example.nova')],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'Vuelta: 1\nVuelta: 2\nVuelta: 3\n')


if __name__ == '__main__':
    unittest.main()
