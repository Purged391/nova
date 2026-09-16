"""Behavior tests for lexical rules, indentation, and diagnostics."""

import unittest

from lexer import Lexer, LexerError, TokenKind as K


class LexerTests(unittest.TestCase):
    def kinds(self, source):
        return [token.kind for token in Lexer(source).tokenize()]

    def test_assignment_and_equality(self):
        self.assertEqual(self.kinds("let x = 2 == 3"),
                         [K.LET, K.IDENTIFIER, K.EQUAL, K.NUMBER,
                          K.EQUAL_EQUAL, K.NUMBER, K.NEWLINE, K.EOF])

    def test_inputs_keyword_and_parameter_list(self):
        self.assertEqual(self.kinds("inputs a: number, b: number"),
                         [K.INPUTS, K.IDENTIFIER, K.COLON, K.NUMBER_TYPE,
                          K.COMMA, K.IDENTIFIER, K.COLON, K.NUMBER_TYPE,
                          K.NEWLINE, K.EOF])
        tokens = Lexer("input inputs_value").tokenize()
        self.assertEqual([t.kind for t in tokens[:2]],
                         [K.IDENTIFIER, K.IDENTIFIER])

    def test_keyword_boundaries(self):
        tokens = Lexer("if iffy true false number").tokenize()
        self.assertEqual([t.kind for t in tokens[:5]],
                         [K.IF, K.IDENTIFIER, K.TRUE, K.FALSE, K.NUMBER_TYPE])
        self.assertIs(tokens[2].value, True)
        self.assertIs(tokens[3].value, False)

    def test_nested_blocks_and_blank_lines(self):
        source = "func main:\n    if true:\n        return 1\n\n # ignored\n    return 2"
        kinds = self.kinds(source)
        self.assertEqual(kinds.count(K.INDENT), 2)
        self.assertEqual(kinds.count(K.DEDENT), 2)
        self.assertEqual(kinds[-3:], [K.NEWLINE, K.DEDENT, K.EOF])
        self.assertEqual(kinds[kinds.index(K.DEDENT) + 1], K.RETURN)

    def test_parenthesized_continuation(self):
        self.assertEqual(self.kinds("let x = (1 +\n    2)"),
                         [K.LET, K.IDENTIFIER, K.EQUAL, K.LEFT_PAREN,
                          K.NUMBER, K.PLUS, K.NUMBER, K.RIGHT_PAREN, K.NEWLINE, K.EOF])

    def test_literal_values(self):
        tokens = Lexer('12 3.5 "Hola, ñ # \\n\\t\\\"\\\\"').tokenize()
        self.assertEqual([t.value for t in tokens[:3]], [12, 3.5, 'Hola, ñ # \n\t"\\'])

    def test_line_endings_and_exclusive_positions(self):
        for newline in ("\n", "\r\n", "\r"):
            tokens = Lexer("let x = 12" + newline + "return x").tokenize()
            span = tokens[3].source_span
            self.assertEqual((span.start_line, span.start_column, span.end_column), (1, 9, 11))
            span = tokens[5].source_span
            self.assertEqual((span.start_line, span.start_column), (2, 1))

    def test_empty_and_comment_only(self):
        for source in ("", "  # comment\n\n"):
            self.assertEqual(self.kinds(source), [K.EOF])

    def test_invalid_input(self):
        cases = ["@", "12abc", "1.2.3", "2.", '"unterminated',
                 '"bad\\q"', '"line\nbreak"', "\tlet x = 1",
                 "if true:\n    return 1\n  return 2", "(", ")", "ñ"]
        for source in cases:
            with self.subTest(source=source), self.assertRaises(LexerError):
                Lexer(source).tokenize()

    def test_error_position(self):
        with self.assertRaises(LexerError) as context:
            Lexer("let x = 1\n  @").tokenize()
        self.assertEqual((context.exception.line, context.exception.column), (2, 3))

    def test_repeatable_scan(self):
        lexer = Lexer("return 1")
        self.assertEqual(lexer.tokenize(), lexer.tokenize())


if __name__ == "__main__":
    unittest.main()

