"""Test operator precedence, types, and short-circuit effects."""
from contextlib import redirect_stdout
from io import StringIO
import unittest

import ast_nodes as ast
from interpreter import run, NovaRuntimeError
from lexer import Lexer, LexerError, TokenKind as K
from parser import parse, ParseError

def source(expression):
    return 'func main:\n    run:\n        return ' + expression

class OperatorTests(unittest.TestCase):
    def test_tokens(self):
        tokens = Lexer('!= <= >= == < > = and or not android origin notice').tokenize()
        self.assertEqual([t.kind for t in tokens[:-2]], [K.NOT_EQUAL, K.LESS_EQUAL,
            K.GREATER_EQUAL, K.EQUAL_EQUAL, K.LESS, K.GREATER, K.EQUAL,
            K.AND, K.OR, K.NOT, K.IDENTIFIER, K.IDENTIFIER, K.IDENTIFIER])
        self.assertEqual(tokens[0].source_span, ast.SourceSpan(1, 1, 1, 3))
        with self.assertRaises(LexerError):
            Lexer('!').tokenize()

    def test_values_and_precedence(self):
        for text, expected in [('-5', -5), ('--5', 5), ('2 * -3 + 1', -5),
            ('-(2 + 3)', -5), ('3--2', 5), ('2 <= 2', True), ('2 >= 3', False),
            ('2 != 2.0', False), ('"a" != "b"', True), ('false != true', True),
            ('not 2 == 3', True), ('not not true', True),
            ('true or false and false', True), ('not false and false', False),
            ('(true or false) and false', False)]:
            with self.subTest(text=text):
                self.assertEqual(run(source(text)), expected)

    def test_unary_ast(self):
        node = parse(source('-5')).functions[0].run_block.statements[0].value
        self.assertIsInstance(node, ast.UnaryExpr)
        self.assertEqual(node.operator, 'NEG')
        self.assertEqual(node.source_span, ast.SourceSpan(3, 16, 3, 18))
        self.assertEqual(node.to_dict()['operand']['value'], 5)

    def test_truth_tables(self):
        for left in (True, False):
            for right in (True, False):
                for op, expected in [('and', left and right), ('or', left or right)]:
                    value = run(source(f'{str(left).lower()} {op} {str(right).lower()}'))
                    self.assertIs(value, expected)

    def test_skipped_errors(self):
        self.assertIs(run(source('false and 1 / 0 > 2')), False)
        self.assertIs(run(source('true or missing()')), True)
        self.assertIs(run(source('false and 1')), False)
        with self.assertRaises(ParseError):
            parse(source('true or (1 +)'))

    def test_call_effects(self):
        helper = 'func check:\n    run:\n        print("called")\n        return true\n'
        for text, output in [('false and check()', ''), ('true or check()', ''),
                             ('true and check()', 'called\n'), ('false or check()', 'called\n')]:
            stream = StringIO()
            with redirect_stdout(stream):
                run(helper + source(text))
            self.assertEqual(stream.getvalue(), output)

    def test_type_errors(self):
        for text in ['not 1', '-true', '-"a"', '1 and true', '1 or true',
                     'true and 1', 'false or 1', 'true != 1', '"a" <= "b"',
                     'true >= false']:
            with self.subTest(text=text), self.assertRaises(NovaRuntimeError):
                run(source(text))

    def test_missing_operands(self):
        for text in ['not', '-', 'true and', 'or true', '1 !=', '1 <=']:
            with self.subTest(text=text), self.assertRaises(ParseError):
                parse(source(text))

if __name__ == '__main__':
    unittest.main()
