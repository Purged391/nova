"""Recursive-descent parser for Nova v0.1."""

from __future__ import annotations

import ast_nodes as ast
from lexer import Lexer, Token, TokenKind as K


class ParseError(ValueError):
    """A syntax error at the first unexpected token."""

    def __init__(self, message: str, token: Token):
        self.token = token
        self.line = token.source_span.start_line
        self.column = token.source_span.start_column
        super().__init__(f"{message}; found {token.kind.name} "
                         f"at line {self.line}, column {self.column}")


def _span(first, last) -> ast.SourceSpan:
    """Join the positions of two tokens or parser-created nodes."""
    start, end = first.source_span, last.source_span
    return ast.SourceSpan(start.start_line, start.start_column,
                          end.end_line, end.end_column)


class Parser:
    """Consume lexer tokens and build the existing AST dataclasses."""

    def __init__(self, tokens: list[Token]):
        if not tokens or tokens[-1].kind != K.EOF:
            raise ValueError("Token stream must end with EOF")
        if any(token.kind == K.EOF for token in tokens[:-1]):
            raise ValueError("EOF must only appear at the end of the token stream")
        self.tokens = tokens
        self.index = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def _match(self, kind: K) -> bool:
        if self.current.kind == kind:
            self._advance()
            return True
        return False

    def _advance(self) -> Token:
        token = self.current
        if token.kind != K.EOF:
            self.index += 1
        return token

    def _expect(self, kind: K, message: str) -> Token:
        if self.current.kind != kind:
            raise ParseError(message, self.current)
        return self._advance()

    def parse(self) -> ast.Program:
        """Parse an entire file; an empty file is a valid empty program."""
        self.index = 0
        start = self.current
        functions = []
        while self.current.kind != K.EOF:
            functions.append(self.parse_function())
        return ast.Program(functions=functions,
                           source_span=_span(start, functions[-1] if functions else start))

    def parse_function(self) -> ast.FuncDecl:
        start = self._expect(K.FUNC, "Expected 'func'")
        name = self._expect(K.IDENTIFIER, "Expected a function name")
        self._expect(K.COLON, "Expected ':' after function name")
        self._expect(K.NEWLINE, "Expected a newline after function header")
        self._expect(K.INDENT, "Expected an indented function body")
        inputs = []
        if self._match(K.INPUTS):
            while True:
                param = self._expect(K.IDENTIFIER, "Expected a parameter name")
                self._expect(K.COLON, "Expected ':' after parameter name")
                type_ref = self._parse_type()
                inputs.append(ast.InputParam(name=param.lexeme, type_name=type_ref,
                                              source_span=_span(param, type_ref)))
                if not self._match(K.COMMA):
                    break
            self._expect(K.NEWLINE, "Expected a newline after inputs")
        self._expect(K.RUN, "Expected one 'run' block after optional inputs")
        block = self._parse_block()
        self._expect(K.DEDENT, "Expected the end of the function after 'run'")
        return ast.FuncDecl(name=name.lexeme, inputs=inputs, run_block=block,
                            source_span=_span(start, block))

    def _parse_type(self) -> ast.TypeRef:
        if self.current.kind not in (K.NUMBER_TYPE, K.TEXT_TYPE, K.BOOL_TYPE):
            raise ParseError("Expected a type: number, text, or bool", self.current)
        token = self._advance()
        return ast.TypeRef(name=token.lexeme, source_span=token.source_span)

    def _parse_block(self) -> ast.BlockStmt:
        """Read a colon followed by a nonempty indented statement block."""
        self._expect(K.COLON, "Expected ':' before block")
        self._expect(K.NEWLINE, "Expected a newline before block")
        self._expect(K.INDENT, "Expected an indented block")
        start = self.current
        statements = []
        while self.current.kind not in (K.DEDENT, K.EOF):
            statements.append(self.parse_statement())
        if not statements:
            raise ParseError("Expected at least one statement", self.current)
        self._expect(K.DEDENT, "Expected the end of the block")
        return ast.BlockStmt(statements=statements, source_span=_span(start, statements[-1]))

    def parse_statement(self) -> ast.Stmt:
        start = self.current
        if self._match(K.LET):
            name = self._expect(K.IDENTIFIER, "Expected a variable name after 'let'")
            declared_type = self._parse_type() if self._match(K.COLON) else None
            self._expect(K.EQUAL, "Expected '=' in variable declaration")
            value = self.parse_expression()
            result = ast.LetStmt(name=name.lexeme, declared_type=declared_type, value=value,
                                 source_span=_span(start, value))
        elif self._match(K.RETURN):
            value = self.parse_expression()
            result = ast.ReturnStmt(value=value, source_span=_span(start, value))
        elif self._match(K.WHILE):
            condition = self.parse_expression()
            block = self._parse_block()
            return ast.WhileStmt(condition=condition, block=block,
                                 source_span=_span(start, block))
        elif self.current.kind == K.IF:
            return self._parse_if()
        elif self.current.kind == K.IDENTIFIER and self.tokens[self.index + 1].kind == K.LEFT_PAREN:
            call = self._primary()
            result = ast.ExprStmt(expression=call, source_span=call.source_span)
        elif self._match(K.IDENTIFIER):
            target = ast.IdentifierExpr(name=start.lexeme, source_span=start.source_span)
            self._expect(K.EQUAL, "Expected '=' after assignment target")
            value = self.parse_expression()
            result = ast.AssignStmt(target=target, value=value, source_span=_span(start, value))
        else:
            raise ParseError("Expected let, assignment, call, if, while, or return", start)
        self._expect(K.NEWLINE, "Expected a newline after statement")
        return result

    def _parse_if(self) -> ast.IfStmt:
        start = self._expect(K.IF, "Expected 'if'")
        condition = self.parse_expression()
        then_block = self._parse_block()
        clauses = []
        else_block = None
        last = then_block
        while self.current.kind == K.ELSE:
            clause_start = self._advance()
            if self._match(K.IF):
                clause_condition = self.parse_expression()
                last = self._parse_block()
                clauses.append(ast.ElseIfClause(condition=clause_condition, block=last,
                                                source_span=_span(clause_start, last)))
            else:
                else_block = self._parse_block()
                last = else_block
                break
        return ast.IfStmt(condition=condition, then_block=then_block,
                          else_if_clauses=clauses, else_block=else_block,
                          source_span=_span(start, last))

    def parse_expression(self) -> ast.Expr:
        """Parse precedence levels from weakest (equality) to strongest."""
        return self._binary(self._comparison, {K.EQUAL_EQUAL: "EQ"})

    def _comparison(self) -> ast.Expr:
        return self._binary(self._addition, {K.GREATER: "GT", K.LESS: "LT"})

    def _addition(self) -> ast.Expr:
        return self._binary(self._multiplication, {K.PLUS: "ADD", K.MINUS: "SUB"})

    def _multiplication(self) -> ast.Expr:
        return self._binary(self._primary, {K.STAR: "MUL", K.SLASH: "DIV"})

    def _binary(self, operand_parser, operators) -> ast.Expr:
        """Build left-associative trees within one precedence level."""
        left = operand_parser()
        while self.current.kind in operators:
            operator = operators[self._advance().kind]
            right = operand_parser()
            left = ast.BinaryExpr(left=left, operator=operator, right=right,
                                  source_span=_span(left, right))
        return left

    def _primary(self) -> ast.Expr:
        token = self.current
        if self._match(K.NUMBER):
            return ast.NumberLiteralExpr(value=token.value, source_span=token.source_span)
        if self._match(K.TEXT):
            return ast.TextLiteralExpr(value=token.value, source_span=token.source_span)
        if self._match(K.TRUE) or self._match(K.FALSE):
            return ast.BoolLiteralExpr(value=token.value, source_span=token.source_span)
        if self._match(K.IDENTIFIER):
            identifier = ast.IdentifierExpr(name=token.lexeme, source_span=token.source_span)
            if self._match(K.LEFT_PAREN):
                arguments = []
                if self.current.kind != K.RIGHT_PAREN:
                    while True:
                        arguments.append(self.parse_expression())
                        if not self._match(K.COMMA):
                            break
                end = self._expect(K.RIGHT_PAREN, "Expected ')' after arguments")
                return ast.CallExpr(callee=identifier, arguments=arguments,
                                    source_span=_span(token, end))
            return identifier
        if self._match(K.LEFT_PAREN):
            expression = self.parse_expression()
            end = self._expect(K.RIGHT_PAREN, "Expected ')' after expression")
            return ast.GroupedExpr(expression=expression, source_span=_span(token, end))
        raise ParseError("Expected a literal, identifier, or parenthesized expression", token)


def parse(source: str) -> ast.Program:
    """Tokenize and parse Nova source text into a Program."""
    return Parser(Lexer(source).tokenize()).parse()
