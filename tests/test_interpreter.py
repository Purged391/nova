"""End-to-end execution tests for Nova runtime behavior."""

import unittest

from examples.example_parser import SOURCE
from interpreter import Interpreter, NovaRuntimeError, run
from parser import parse


def execute(body):
    return run("func main:\n    run:\n" + "\n".join("        " + line for line in body.splitlines()))


class InterpreterTests(unittest.TestCase):
    def test_user_examples(self):
        interpreter = Interpreter(parse(SOURCE))
        self.assertEqual(interpreter.call("sum", 2, 3), 5)
        self.assertEqual(interpreter.call("sum", 1.5, 2), 3.5)
        self.assertEqual(interpreter.call("sayHello"), "Hola")

    def test_operators(self):
        for expression, expected in [("2 + 3 * 4", 14), ("(2 + 3) * 4", 20),
                                     ("10 - 3 - 2", 5), ("5 / 2", 2.5),
                                     ("2 > 1", True), ("2 < 1", False),
                                     ("2 == 2.0", True), ('"a" + "b"', "ab"),
                                     ('"a" == "b"', False), ("false == false", True)]:
            with self.subTest(expression=expression):
                self.assertEqual(execute("return " + expression), expected)

    def test_branch_selection(self):
        source = '''func choose:
    inputs x: number
    run:
        if x > 0:
            return "positive"
        else if x == 0:
            return "zero"
        else:
            return "negative"
'''
        for value, expected in [(1, "positive"), (0, "zero"), (-1, "negative")]:
            self.assertEqual(run(source, "choose", value), expected)

    def test_nested_return_and_unexecuted_code(self):
        self.assertEqual(execute("if true:\n    if true:\n        return 7\nreturn 1 / 0"), 7)
        self.assertEqual(execute("if false:\n    return missing\nreturn 8"), 8)
        self.assertEqual(execute("if true:\n    return 1\nelse if missing:\n    return 2"), 1)

    def test_block_scope_and_assignment(self):
        self.assertEqual(execute("let x = 1\nif true:\n    x = 2\nreturn x"), 2)
        self.assertEqual(execute("let x = 1\nif true:\n    let x = 2\n    x = 3\nreturn x"), 1)
        with self.assertRaisesRegex(NovaRuntimeError, "Undefined variable"):
            execute("if true:\n    let x = 2\nreturn x")

    def test_invocations_are_isolated(self):
        source = "func f:\n    inputs x: number\n    run:\n        x = x + 1\n        return x"
        interpreter = Interpreter(parse(source))
        self.assertEqual(interpreter.call("f", 1), 2)
        self.assertEqual(interpreter.call("f", 1), 2)
        with self.assertRaises(NovaRuntimeError):
            interpreter.call("f", "bad")
        self.assertEqual(interpreter.call("f", 2), 3)

    def test_fallthrough(self):
        self.assertIsNone(execute("let x = 1"))
        self.assertIsNone(execute("if false:\n    return 1"))

    def test_argument_validation(self):
        interpreter = Interpreter(parse(SOURCE))
        for args in [(), (1,), (1, 2, 3), (True, 2), ("1", 2), (None, 2),
                     (float("inf"), 2), (float("nan"), 2), ([], 2)]:
            with self.subTest(args=args), self.assertRaises(NovaRuntimeError):
                interpreter.call("sum", *args)
        with self.assertRaisesRegex(NovaRuntimeError, "Undefined function"):
            interpreter.call("missing")

    def test_runtime_type_errors(self):
        cases = ['let x: number = "a"', 'let x = 1\nx = "a"',
                 "let x: number = true", "if 1:\n    return 2",
                 "return true + 1", 'return "a" + 1', 'return "a" * 2',
                 "return true == 1", 'return "a" < "b"',
                 "return 1 / 0", "return 1 / 0.0", "return missing", "x = 1",
                 "let x = 1\nlet x = 2"]
        for body in cases:
            with self.subTest(body=body), self.assertRaises(NovaRuntimeError):
                execute(body)

    def test_duplicate_declarations(self):
        with self.assertRaisesRegex(NovaRuntimeError, "Duplicate function"):
            Interpreter(parse(SOURCE + SOURCE))
        with self.assertRaisesRegex(NovaRuntimeError, "Duplicate parameter"):
            run("func f:\n    inputs a: number, a: text\n    run:\n        return a", "f", 1, "a")
        with self.assertRaisesRegex(NovaRuntimeError, "already declared"):
            run("func f:\n    inputs a: number\n    run:\n        let a = 2", "f", 1)

    def test_numeric_overflow(self):
        source = "func f:\n    inputs x: number\n    run:\n        return x * x"
        with self.assertRaises(NovaRuntimeError):
            run(source, "f", 1e308)

    def test_error_position(self):
        with self.assertRaises(NovaRuntimeError) as context:
            execute("return 1 / 0")
        self.assertEqual((context.exception.line, context.exception.column), (3, 16))
        self.assertIn("Division by zero", str(context.exception))


if __name__ == "__main__":
    unittest.main()
