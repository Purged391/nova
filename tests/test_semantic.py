"""Static checking and public execution pipeline regression tests."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from interpreter import run, NovaRuntimeError
from parser import parse
from semantic import analyze, SemanticError, UNKNOWN, VOID


def source(body):
    return 'func main:\n    run:\n' + '\n'.join('        ' + line for line in body.splitlines())


class SemanticTests(unittest.TestCase):
    def test_all_examples_and_ast_unchanged(self):
        root = Path(__file__).resolve().parents[1]
        for path in (root / 'examples').glob('*.nova'):
            with self.subTest(path=path.name):
                program = parse(path.read_text(encoding='utf-8-sig'))
                before = program.to_dict()
                analyze(program)
                self.assertEqual(program.to_dict(), before)

    def test_known_types(self):
        for body in ['let x: number = "bad"', 'let x = 1\nx = "bad"',
                     'return true + 1', 'return not 1', 'if 1:\n    print()',
                     'while "yes":\n    break', 'return true == 1', 'return -false',
                     'return false and 1', 'return true or "yes"']:
            with self.subTest(body=body), self.assertRaises(SemanticError):
                analyze(parse(source(body)))

    def test_unknown_names_and_scope(self):
        for body in ['return missing', 'x = 2', 'let x = x',
                     'if true:\n    let x = 1\nreturn x',
                     'while false:\n    let x = 1\nreturn x', 'missing()']:
            with self.subTest(body=body), self.assertRaises(SemanticError):
                analyze(parse(source(body)))

    def test_shadowing_and_assignment(self):
        self.assertEqual(run(source('let x = 1\nif true:\n    let x = "inner"\nreturn x')), 1)
        self.assertEqual(run(source('let x = 1\nif true:\n    x = 2\nreturn x')), 2)
        with self.assertRaises(SemanticError):
            analyze(parse(source('let x = 1\nif false:\n    x = "bad"')))

    def test_duplicates(self):
        cases = [source('let x = 1\nlet x = 2'), source('return 1') + '\n' + source('return 2'),
                 'func f:\n    inputs a: number, a: text\n    run:\n        return a',
                 'func f:\n    inputs a: number\n    run:\n        let a = 1',
                 'func print:\n    run:\n        return 1']
        for text in cases:
            with self.subTest(text=text), self.assertRaises(SemanticError):
                analyze(parse(text))

    def test_unreachable_and_unused_functions(self):
        for text in [source('if false:\n    print(missing)'), source('return 1\nprint(missing)'),
                     source('return true or missing()'),
                     source('return 1') + '\nfunc unused:\n    run:\n        return missing']:
            with self.subTest(text=text), self.assertRaises(SemanticError):
                analyze(parse(text))

    def test_no_effects_before_failure(self):
        output = StringIO()
        with redirect_stdout(output), self.assertRaises(SemanticError):
            run(source('print("must not print")\nlet x: number = "bad"'))
        self.assertEqual(output.getvalue(), '')

    def test_calls_and_forward_inference(self):
        functions = 'func first:\n    run:\n        return second()\nfunc second:\n    run:\n        return 2\n'
        summaries = analyze(parse(functions)).return_types
        self.assertEqual(summaries, {'first': 'number', 'second': 'number'})
        with self.assertRaises(SemanticError):
            run(functions + source('let x: text = first()'))
        typed = 'func f:\n    inputs x: number\n    run:\n        return x\n'
        for call in ['f()', 'f(1, 2)', 'f("a")']:
            with self.subTest(call=call), self.assertRaises(SemanticError):
                run(typed + source(call))

    def test_call_type_inference_across_local_variables(self):
        text = 'func sum:\n    inputs a: number, b: number\n    run:\n        let result = a + b\n        return result'
        self.assertEqual(analyze(parse(text)).return_types['sum'], 'number')

    def test_void_values(self):
        function = 'func f:\n    run:\n        print("hello")\n'
        self.assertEqual(analyze(parse(function)).return_types['f'], VOID)
        for call in ['f()', 'print()']:
            with self.subTest(call=call), self.assertRaises(SemanticError):
                analyze(parse(function + source('let x = ' + call)))
        analyze(parse(function + source('f()')))

    def test_conservative_returns_and_runtime_checks(self):
        function = 'func maybe:\n    inputs flag: bool\n    run:\n        if flag:\n            return 1\n'
        self.assertEqual(analyze(parse(function)).return_types['maybe'], UNKNOWN)
        self.assertEqual(run(function + source('return maybe(true)')), 1)
        with self.assertRaises(NovaRuntimeError):
            run(function + source('return maybe(false)'))
        mixed = 'func mixed:\n    inputs flag: bool\n    run:\n        if flag:\n            return 1\n        else:\n            return "a"\n'
        self.assertEqual(analyze(parse(mixed)).return_types['mixed'], UNKNOWN)
        with self.assertRaises(NovaRuntimeError):
            run(mixed + source('let x: number = mixed(false)'))

    def test_return_flow(self):
        both = 'if true:\n    return 1\nelse:\n    return 2'
        self.assertEqual(analyze(parse(source(both))).return_types['main'], 'number')
        partial = 'while true:\n    if true:\n        break\n    return 1'
        self.assertEqual(analyze(parse(source(partial))).return_types['main'], UNKNOWN)

    def test_recursion(self):
        text = 'func f:\n    inputs n: number\n    run:\n        if n == 0:\n            return 1\n        return n * f(n - 1)'
        self.assertEqual(analyze(parse(text)).return_types['f'], 'number')
        self.assertEqual(run(text, 'f', 5), 120)
        mutual = 'func a:\n    run:\n        return b()\nfunc b:\n    run:\n        return a()'
        self.assertEqual(analyze(parse(mutual)).return_types, {'a': UNKNOWN, 'b': UNKNOWN})

    def test_runtime_short_circuit_preserved(self):
        self.assertIs(run(source('return false and 10 / 0 > 2')), False)
        self.assertIs(run(source('return true or 10 / 0 > 2')), True)
        analyze(parse(source('return 10 / 0')))
        with self.assertRaises(NovaRuntimeError):
            run(source('return 10 / 0'))

    def test_diagnostic_position(self):
        with self.assertRaises(SemanticError) as caught:
            analyze(parse(source('let x: number = "bad"')))
        self.assertEqual((caught.exception.line, caught.exception.column), (3, 9))

    def test_cli_check_never_executes_and_needs_no_main(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'check.nova'
            path.write_text('func f:\n    run:\n        while true:\n            print("never")', encoding='utf-8')
            result = subprocess.run([sys.executable, str(root / 'nova.py'), '--check', str(path)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, 'Check passed\n')
            path.write_text(source('print("never")\nreturn missing'), encoding='utf-8')
            for options in [[], ['--check']]:
                result = subprocess.run([sys.executable, str(root / 'nova.py'), *options, str(path)],
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, '')
                self.assertIn('SemanticError', result.stderr)
                self.assertIn('^', result.stderr)


if __name__ == '__main__':
    unittest.main()
