"""Test source-to-AST behavior and syntax diagnostics."""

import unittest

import ast_nodes as ast
from examples.example_parser import SOURCE
from lexer import Lexer
from parser import Parser, ParseError, parse


def expression(source):
    return parse("func main:\n    run:\n        return " + source).functions[0].run_block.statements[0].value


class ParserTests(unittest.TestCase):
    def test_user_examples(self):
        program = parse(SOURCE)
        first, second = program.functions
        self.assertEqual(first.name, "sum")
        self.assertEqual([(p.name, p.type_name.name) for p in first.inputs],
                         [("a", "number"), ("b", "number")])
        declaration, result = first.run_block.statements
        self.assertEqual(declaration.declared_type.name, "number")
        self.assertEqual(declaration.value.operator, "ADD")
        self.assertEqual(result.value.name, "result")
        self.assertEqual(second.inputs, [])
        self.assertEqual(second.run_block.statements[0].value.value, "Hola")

    def test_precedence_and_associativity(self):
        tree = expression("10 - 3 - 2 * 4")
        self.assertEqual(tree.operator, "SUB")
        self.assertEqual(tree.left.operator, "SUB")
        self.assertEqual(tree.right.operator, "MUL")
        tree = expression("1 + 2 < 4 == true")
        self.assertEqual(tree.operator, "EQ")
        self.assertEqual(tree.left.operator, "LT")
        self.assertEqual(tree.left.left.operator, "ADD")

    def test_grouping_and_literals(self):
        tree = expression("(1 +\n          2) / 3.5")
        self.assertIsInstance(tree.left, ast.GroupedExpr)
        self.assertEqual(tree.left.expression.operator, "ADD")
        self.assertEqual(tree.right.value, 3.5)
        self.assertIs(expression("false").value, False)
        self.assertEqual(expression('"a\\nb"').value, "a\nb")

    def test_assignment_and_untyped_declaration(self):
        block = parse("func main:\n    run:\n        let x = 1\n        x = 2\n").functions[0].run_block
        self.assertIsNone(block.statements[0].declared_type)
        self.assertIsInstance(block.statements[1], ast.AssignStmt)
        self.assertEqual(block.statements[1].target.name, "x")

    def test_nested_conditionals(self):
        source = '''func main:
    run:
        if true:
            if false:
                return 1
            else:
                return 2
        else if false:
            return 3
        else if true:
            return 4
        else:
            return 5
        return 6
'''
        statements = parse(source).functions[0].run_block.statements
        outer = statements[0]
        self.assertEqual(len(outer.else_if_clauses), 2)
        self.assertEqual(outer.else_block.statements[0].value.value, 5)
        inner = outer.then_block.statements[0]
        self.assertEqual(inner.else_if_clauses, [])
        self.assertEqual(inner.else_block.statements[0].value.value, 2)
        self.assertEqual(statements[1].value.value, 6)

    def test_if_without_else(self):
        node = parse("func f:\n    run:\n        if true:\n            return 1").functions[0].run_block.statements[0]
        self.assertEqual(node.else_if_clauses, [])
        self.assertIsNone(node.else_block)

    def test_spans(self):
        node = expression("2 + 3")
        self.assertEqual(node.source_span, ast.SourceSpan(3, 16, 3, 21))
        self.assertEqual(node.right.source_span, ast.SourceSpan(3, 20, 3, 21))
        program = parse(SOURCE)
        self.assertEqual(program.functions[0].source_span, ast.SourceSpan(1, 1, 5, 22))
        self.assertIn("source_span", program.to_dict())

    def test_empty_and_comments(self):
        self.assertEqual(parse("# empty\n").functions, [])
        self.assertEqual(len(parse(SOURCE.replace("\n", "\r\n")).functions), 2)

    def test_invalid_function_structure(self):
        cases = ["let x = 1", "func f\n    run:\n        return 1",
                 "func f:\n    inputs a: number\n", "func f:\n    run:\n",
                 "func f:\n    inputs\n    run:\n        return 1",
                 "func f:\n    inputs a: number,\n    run:\n        return 1",
                 "func f:\n    inputs a: unknown\n    run:\n        return 1",
                 "func f:\n    inputs a number\n    run:\n        return 1",
                 "func f:\n    run:\n        return 1\n    run:\n        return 2",
                 "func f:\n    input a: number\n    run:\n        return 1"]
        for source in cases:
            with self.subTest(source=source), self.assertRaises(ParseError):
                parse(source)

    def test_invalid_statements(self):
        for statement in ("return", "let x =", "let x: bool", "x + 1",
                          "return 1 2", "else:"):
            with self.subTest(statement=statement), self.assertRaises(ParseError):
                parse("func f:\n    run:\n        " + statement)

    def test_error_position(self):
        with self.assertRaises(ParseError) as context:
            parse("func f:\n    run:\n        let x 1")
        self.assertEqual((context.exception.line, context.exception.column), (3, 15))
        self.assertIn("Expected '='", str(context.exception))

    def test_token_stream_contract(self):
        with self.assertRaises(ValueError):
            Parser([])
        parser = Parser(Lexer(SOURCE).tokenize())
        self.assertEqual(parser.parse(), parser.parse())


if __name__ == "__main__":
    unittest.main()
