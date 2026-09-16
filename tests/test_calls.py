"""Verify calls, output, scopes, recursion, and CLI integration."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
import sys
import unittest

import ast_nodes as ast
from interpreter import Interpreter, NovaRuntimeError, run
from parser import parse, ParseError


class CallTests(unittest.TestCase):
    def test_ast_and_nested_calls(self):
        source = 'func main:\n    run:\n        print(sum(2, 3))'
        statement = parse(source).functions[0].run_block.statements[0]
        self.assertIsInstance(statement, ast.ExprStmt)
        self.assertIsInstance(statement.expression, ast.CallExpr)
        self.assertEqual(statement.expression.callee.name, 'print')
        self.assertEqual(statement.expression.arguments[0].callee.name, 'sum')
        self.assertEqual(statement.expression.source_span, ast.SourceSpan(3, 9, 3, 25))

    def test_example_cli(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, str(root / 'nova.py'), str(root / 'examples' / 'calls.nova')],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'Hola, Nova\nResultado: 5\nCorrecto: true\n')

    def test_forward_reference_recursion(self):
        source = '''func main:
    run:
        return factorial(5) + factorial(0)
func factorial:
    inputs n: number
    run:
        if n == 0:
            return 1
        return n * factorial(n - 1)
'''
        self.assertEqual(run(source), 121)

    def test_output_and_argument_order(self):
        source = '''func mark:
    inputs n: number
    run:
        print(n)
        return n
func main:
    run:
        print(mark(1), mark(2), false)
        print()
        return 7
'''
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(run(source), 7)
        self.assertEqual(output.getvalue(), '1\n2\n1 2 false\n\n')

    def test_callee_cannot_access_caller_locals(self):
        source = 'func f:\n    run:\n        return x\nfunc main:\n    run:\n        let x = 2\n        return f()'
        with self.assertRaisesRegex(NovaRuntimeError, 'Undefined variable'):
            run(source)

    def test_call_errors_have_call_positions(self):
        function = 'func f:\n    inputs a: number\n    run:\n        return a\n'
        for expression in ['missing()', 'f()', 'f(true)', 'f(1, 2)']:
            with self.subTest(expression=expression), self.assertRaises(NovaRuntimeError) as caught:
                run(function + 'func main:\n    run:\n        return ' + expression)
            self.assertEqual(caught.exception.line, 7)
            self.assertEqual(caught.exception.column, 16)

    def test_no_value_and_discarded_results(self):
        source = 'func f:\n    run:\n        let x = 1\n'
        self.assertIsNone(run(source + 'func main:\n    run:\n        f()'))
        for expression in ['f()', 'print()']:
            with redirect_stdout(StringIO()), self.assertRaisesRegex(NovaRuntimeError, 'did not return a value'):
                run(source + 'func main:\n    run:\n        let x = ' + expression)

    def test_depth_error_and_recovery(self):
        source = 'func f:\n    run:\n        f()\nfunc ok:\n    run:\n        return 1'
        runtime = Interpreter(parse(source))
        with self.assertRaisesRegex(NovaRuntimeError, 'call depth'):
            runtime.call('f')
        self.assertEqual(runtime.call('ok'), 1)

    def test_reserved_builtin(self):
        with self.assertRaisesRegex(NovaRuntimeError, 'reserved'):
            run('func print:\n    run:\n        return 1')

    def test_malformed_calls(self):
        for expression in ['f(,)', 'f(1,)', 'f(1 2)', 'f()()']:
            with self.subTest(expression=expression), self.assertRaises(ParseError):
                parse('func main:\n    run:\n        return ' + expression)


if __name__ == '__main__':
    unittest.main()
