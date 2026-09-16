"""Conservative name, scope, and type analysis for the Nova core."""

from __future__ import annotations

from dataclasses import dataclass
import ast_nodes as ast


UNKNOWN = "unknown"
VOID = "void"


class SemanticError(Exception):
    """The first statically detectable error, with its source position."""

    def __init__(self, message: str, node: ast.NodeBase):
        self.source_span = node.source_span
        self.line = self.source_span.start_line if self.source_span else None
        self.column = self.source_span.start_column if self.source_span else None
        location = f" at line {self.line}, column {self.column}" if self.source_span else ""
        super().__init__(message + location)


class _Scope:
    def __init__(self, parent: _Scope | None = None):
        self.parent = parent
        self.names: dict[str, str] = {}

    def declare(self, name: str, type_name: str, node: ast.NodeBase) -> None:
        if name in self.names:
            raise SemanticError(f"Variable '{name}' is already declared in this scope", node)
        self.names[name] = type_name

    def lookup(self, name: str, node: ast.NodeBase) -> str:
        if name in self.names:
            return self.names[name]
        if self.parent is not None:
            return self.parent.lookup(name, node)
        raise SemanticError(f"Undefined variable '{name}'", node)


@dataclass
class AnalysisResult:
    """Return summaries are primitive types, unknown, or internal void."""

    return_types: dict[str, str]


def _expect(actual: str, expected: str, node: ast.NodeBase) -> None:
    if actual != UNKNOWN and expected != UNKNOWN and actual != expected:
        raise SemanticError(f"Expected {expected}, got {actual}", node)


class SemanticAnalyzer:
    """Analyze all functions without running code or mutating the AST."""

    def analyze(self, program: ast.Program) -> AnalysisResult:
        self.functions: dict[str, ast.FuncDecl] = {}
        for function in program.functions:
            if function.name == "print":
                raise SemanticError("Function name 'print' is reserved for console output", function)
            if function.name in self.functions:
                raise SemanticError(f"Duplicate function '{function.name}'", function)
            seen = set()
            for parameter in function.inputs:
                if parameter.name in seen:
                    raise SemanticError(f"Duplicate parameter '{parameter.name}'", parameter)
                seen.add(parameter.name)
            self.functions[function.name] = function
        self.summaries = {name: UNKNOWN for name in self.functions}
        # Information propagates along forward calls. Recursive cycles may stay unknown.
        for _ in range(len(self.functions) + 2):
            updated = {name: self._function(function) for name, function in self.functions.items()}
            if updated == self.summaries:
                break
            self.summaries = updated
        return AnalysisResult(dict(self.summaries))

    def _function(self, function: ast.FuncDecl) -> str:
        scope = _Scope()
        for parameter in function.inputs:
            scope.declare(parameter.name, parameter.type_name.name, parameter)
        self.returns: list[str] = []
        exits = self._block(function.run_block, scope, 0)
        if not self.returns:
            return VOID
        types = set(self.returns)
        if exits == {"return"} and len(types) == 1:
            return self.returns[0]
        return UNKNOWN

    def _block(self, block: ast.BlockStmt, scope: _Scope, loop_depth: int) -> set[str]:
        exits = {"next"}
        for statement in block.statements:
            # Analyze unreachable statements too, but do not change reachable exits.
            statement_exits = self._statement(statement, scope, loop_depth)
            if "next" in exits:
                exits = (exits - {"next"}) | statement_exits
        return exits

    def _statement(self, node: ast.Stmt, scope: _Scope, loop_depth: int) -> set[str]:
        if isinstance(node, ast.LetStmt):
            value_type = self._expression(node.value, scope)
            declared = node.declared_type.name if node.declared_type else value_type
            _expect(value_type, declared, node)
            scope.declare(node.name, declared, node)
        elif isinstance(node, ast.AssignStmt):
            expected = scope.lookup(node.target.name, node.target)
            _expect(self._expression(node.value, scope), expected, node)
        elif isinstance(node, ast.ExprStmt):
            self._call(node.expression, scope, require_value=False)
        elif isinstance(node, ast.ReturnStmt):
            self.returns.append(self._expression(node.value, scope))
            return {"return"}
        elif isinstance(node, ast.BlockStmt):
            return self._block(node, _Scope(scope), loop_depth)
        elif isinstance(node, ast.IfStmt):
            exits = set()
            branches = [(node.condition, node.then_block)]
            branches.extend((clause.condition, clause.block) for clause in node.else_if_clauses)
            for condition, block in branches:
                _expect(self._expression(condition, scope), "bool", condition)
                exits |= self._block(block, _Scope(scope), loop_depth)
            exits |= (self._block(node.else_block, _Scope(scope), loop_depth)
                      if node.else_block else {"next"})
            return exits
        elif isinstance(node, ast.WhileStmt):
            _expect(self._expression(node.condition, scope), "bool", node.condition)
            exits = self._block(node.block, _Scope(scope), loop_depth + 1)
            # A loop may execute zero times; no constant-condition reasoning yet.
            return {"next"} | (exits & {"return"})
        elif isinstance(node, (ast.BreakStmt, ast.ContinueStmt)):
            if loop_depth == 0:
                raise SemanticError("Loop control is only allowed inside a loop", node)
            return {"break" if isinstance(node, ast.BreakStmt) else "continue"}
        else:
            raise SemanticError(f"Unsupported statement: {type(node).__name__}", node)
        return {"next"}

    def _call(self, node: ast.CallExpr, scope: _Scope, require_value: bool = True) -> str:
        name = node.callee.name
        if name != "print" and name not in self.functions:
            raise SemanticError(f"Undefined function '{name}'", node)
        if name != "print":
            function = self.functions[name]
            if len(node.arguments) != len(function.inputs):
                raise SemanticError(f"Function '{name}' expects {len(function.inputs)} arguments, "
                                    f"got {len(node.arguments)}", node)
        arguments = [self._expression(argument, scope) for argument in node.arguments]
        if name == "print":
            result = VOID
        else:
            for actual, parameter in zip(arguments, function.inputs):
                _expect(actual, parameter.type_name.name, node)
            result = self.summaries[name]
        if require_value and result == VOID:
            raise SemanticError(f"Function '{name}' does not return a value", node)
        return result

    def _expression(self, node: ast.Expr, scope: _Scope) -> str:
        if isinstance(node, ast.NumberLiteralExpr):
            return "number"
        if isinstance(node, ast.TextLiteralExpr):
            return "text"
        if isinstance(node, ast.BoolLiteralExpr):
            return "bool"
        if isinstance(node, ast.IdentifierExpr):
            return scope.lookup(node.name, node)
        if isinstance(node, ast.GroupedExpr):
            return self._expression(node.expression, scope)
        if isinstance(node, ast.CallExpr):
            return self._call(node, scope)
        if isinstance(node, ast.UnaryExpr):
            value_type = self._expression(node.operand, scope)
            if node.operator not in ("NEG", "NOT"):
                raise SemanticError(f"Unsupported unary operator: {node.operator}", node)
            expected = "number" if node.operator == "NEG" else "bool"
            _expect(value_type, expected, node.operand)
            return expected
        if isinstance(node, ast.BinaryExpr):
            # Static analysis visits both operands; runtime still short-circuits.
            left = self._expression(node.left, scope)
            right = self._expression(node.right, scope)
            if node.operator in ("AND", "OR"):
                _expect(left, "bool", node.left)
                _expect(right, "bool", node.right)
                return "bool"
            if node.operator in ("EQ", "NE"):
                _expect(right, left, node)
                return "bool"
            if node.operator == "ADD":
                for operand_type in (left, right):
                    if operand_type not in (UNKNOWN, "number", "text"):
                        raise SemanticError("Addition requires two numbers or two text values", node)
                _expect(right, left, node)
                return right if left == UNKNOWN else left
            if node.operator in ("SUB", "MUL", "DIV", "GT", "LT", "GE", "LE"):
                _expect(left, "number", node.left)
                _expect(right, "number", node.right)
                return "bool" if node.operator in ("GT", "LT", "GE", "LE") else "number"
            raise SemanticError(f"Unsupported binary operator: {node.operator}", node)
        raise SemanticError(f"Unsupported expression: {type(node).__name__}", node)


def analyze(program: ast.Program) -> AnalysisResult:
    """Validate a parsed program without requiring a main entry point."""
    return SemanticAnalyzer().analyze(program)
