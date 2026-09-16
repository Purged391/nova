"""Turn Nova source text into tokens without building or executing an AST."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
import math

from ast_nodes import SourceSpan


class TokenKind(Enum):
    """Categories understood by the Nova parser."""

    FUNC = auto()
    INPUTS = auto()
    RUN = auto()
    LET = auto()
    IF = auto()
    WHILE = auto()
    BREAK = auto()
    CONTINUE = auto()
    ELSE = auto()
    RETURN = auto()
    NUMBER_TYPE = auto()
    TEXT_TYPE = auto()
    BOOL_TYPE = auto()
    TRUE = auto()
    FALSE = auto()
    IDENTIFIER = auto()
    NUMBER = auto()
    TEXT = auto()
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    GREATER = auto()
    LESS = auto()
    EQUAL = auto()
    EQUAL_EQUAL = auto()
    LEFT_PAREN = auto()
    RIGHT_PAREN = auto()
    COLON = auto()
    COMMA = auto()
    NEWLINE = auto()
    INDENT = auto()
    DEDENT = auto()
    EOF = auto()


KEYWORDS = {
    "func": TokenKind.FUNC, "inputs": TokenKind.INPUTS, "run": TokenKind.RUN,
    "let": TokenKind.LET, "if": TokenKind.IF, "while": TokenKind.WHILE,
    "break": TokenKind.BREAK, "continue": TokenKind.CONTINUE, "else": TokenKind.ELSE,
    "return": TokenKind.RETURN, "number": TokenKind.NUMBER_TYPE,
    "text": TokenKind.TEXT_TYPE, "bool": TokenKind.BOOL_TYPE,
    "true": TokenKind.TRUE, "false": TokenKind.FALSE,
}

SYMBOLS = {
    "+": TokenKind.PLUS, "-": TokenKind.MINUS, "*": TokenKind.STAR,
    "/": TokenKind.SLASH, ">": TokenKind.GREATER, "<": TokenKind.LESS,
    "=": TokenKind.EQUAL, "(": TokenKind.LEFT_PAREN,
    ")": TokenKind.RIGHT_PAREN, ":": TokenKind.COLON, ",": TokenKind.COMMA,
}


@dataclass(frozen=True)
class Token:
    """Original spelling, decoded literal value, and an exclusive-end span."""

    kind: TokenKind
    lexeme: str
    value: str | int | float | bool | None
    source_span: SourceSpan


class LexerError(ValueError):
    """A lexical error with a one-based source position."""

    def __init__(self, message: str, line: int, column: int):
        self.line = line
        self.column = column
        super().__init__(f"{message} at line {line}, column {column}")


def _digit(char: str) -> bool:
    return bool(char) and "0" <= char <= "9"


def _name_start(char: str) -> bool:
    return bool(char) and ("a" <= char <= "z" or "A" <= char <= "Z" or char == "_")


class Lexer:
    """Scan left to right. Each tokenize() call starts a fresh scan."""

    def __init__(self, source: str):
        self.source = source

    def tokenize(self) -> list[Token]:
        """Add block boundaries and ignore newlines inside parentheses."""
        raw = self._scan()
        result: list[Token] = []
        indents = [0]
        parentheses: list[Token] = []
        at_line_start = True
        for token in raw:
            span = token.source_span
            if token.kind == TokenKind.EOF:
                if parentheses:
                    opening = parentheses[-1].source_span
                    raise LexerError("Unclosed parenthesis", opening.start_line, opening.start_column)
                if result and result[-1].kind != TokenKind.NEWLINE:
                    result.append(Token(TokenKind.NEWLINE, "", None, span))
                while len(indents) > 1:
                    indents.pop()
                    result.append(Token(TokenKind.DEDENT, "", None, span))
                result.append(token)
                break
            if token.kind == TokenKind.NEWLINE:
                if not parentheses and not at_line_start:
                    result.append(token)
                    at_line_start = True
                continue
            if at_line_start and not parentheses:
                indentation = span.start_column - 1
                position = SourceSpan(span.start_line, span.start_column,
                                      span.start_line, span.start_column)
                if indentation > indents[-1]:
                    indents.append(indentation)
                    result.append(Token(TokenKind.INDENT, "", None, position))
                else:
                    while indentation < indents[-1]:
                        indents.pop()
                        result.append(Token(TokenKind.DEDENT, "", None, position))
                    if indentation != indents[-1]:
                        raise LexerError("Indentation does not match an outer block",
                                         span.start_line, span.start_column)
                at_line_start = False
            if token.kind == TokenKind.LEFT_PAREN:
                parentheses.append(token)
            elif token.kind == TokenKind.RIGHT_PAREN:
                if not parentheses:
                    raise LexerError("Unmatched closing parenthesis", span.start_line, span.start_column)
                parentheses.pop()
            result.append(token)
        return result

    def _scan(self) -> list[Token]:
        """Read lexical tokens before applying indentation rules."""
        self.index = 0
        self.line = 1
        self.column = 1
        tokens: list[Token] = []
        while self.index < len(self.source):
            char = self._peek()
            if char == "\t":
                raise LexerError("Use spaces instead of tabs", self.line, self.column)
            if char == " ":
                self._advance()
                continue
            if char == "#":
                while self._peek() and self._peek() not in "\r\n":
                    self._advance()
                continue
            start, line, column = self.index, self.line, self.column
            value = None
            if char in "\r\n":
                self._advance()
                kind = TokenKind.NEWLINE
            elif _name_start(char):
                self._advance()
                while _name_start(self._peek()) or _digit(self._peek()):
                    self._advance()
                word = self.source[start:self.index]
                kind = KEYWORDS.get(word, TokenKind.IDENTIFIER)
                if kind == TokenKind.IDENTIFIER:
                    value = word
                elif kind in (TokenKind.TRUE, TokenKind.FALSE):
                    value = kind == TokenKind.TRUE
            elif _digit(char):
                kind = TokenKind.NUMBER
                value = self._number(line, column)
            elif char == '"':
                kind = TokenKind.TEXT
                value = self._text(line, column)
            elif char == "=" and self._peek(1) == "=":
                self._advance()
                self._advance()
                kind = TokenKind.EQUAL_EQUAL
            elif char in SYMBOLS:
                kind = SYMBOLS[char]
                self._advance()
            else:
                raise LexerError(f"Unexpected character {char!r}", line, column)
            tokens.append(Token(
                kind, self.source[start:self.index], value,
                SourceSpan(line, column, self.line, self.column),
            ))
        tokens.append(Token(TokenKind.EOF, "", None,
                            SourceSpan(self.line, self.column, self.line, self.column)))
        return tokens

    def _peek(self, offset: int = 0) -> str:
        index = self.index + offset
        return self.source[index] if index < len(self.source) else ""

    def _advance(self) -> str:
        char = self.source[self.index]
        self.index += 1
        if char == "\r":
            if self._peek() == "\n":
                self.index += 1
            self.line += 1
            self.column = 1
        elif char == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return char

    def _number(self, line: int, column: int) -> int | float:
        start = self.index
        while _digit(self._peek()):
            self._advance()
        if self._peek() == ".":
            self._advance()
            if not _digit(self._peek()):
                raise LexerError("Expected a digit after the decimal point", self.line, self.column)
            while _digit(self._peek()):
                self._advance()
        if _name_start(self._peek()) or self._peek() == ".":
            raise LexerError("Invalid number literal", self.line, self.column)
        spelling = self.source[start:self.index]
        try:
            value = float(spelling) if "." in spelling else int(spelling)
        except ValueError as error:
            raise LexerError("Number literal is too large", line, column) from error
        if isinstance(value, float) and not math.isfinite(value):
            raise LexerError("Number literal is too large", line, column)
        return value

    def _text(self, line: int, column: int) -> str:
        self._advance()
        result: list[str] = []
        escapes = {"n": "\n", "r": "\r", "t": "\t", '"': '"', "\\": "\\"}
        while self._peek() and self._peek() != '"':
            if self._peek() in "\r\n":
                raise LexerError("Unterminated string literal", line, column)
            if self._peek() == "\\":
                escape_line, escape_column = self.line, self.column
                self._advance()
                char = self._peek()
                if not char:
                    raise LexerError("Unterminated string literal", line, column)
                if char not in escapes:
                    raise LexerError(f"Unknown escape sequence: {char!r}", escape_line, escape_column)
                self._advance()
                result.append(escapes[char])
            else:
                result.append(self._advance())
        if not self._peek():
            raise LexerError("Unterminated string literal", line, column)
        self._advance()
        return "".join(result)

