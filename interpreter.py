"""Tree-walking interpreter for Nova v0.1."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import TypeAlias

import ast_nodes as ast
from parser import parse
from semantic import analyze


Value: TypeAlias = int | float | str | bool


class NovaRuntimeError(Exception):
    """An execution error with source information when available."""

    def __init__(self, message: str, node: ast.NodeBase | None = None):
        self.source_span = node.source_span if node is not None else None
        self.line = self.source_span.start_line if self.source_span else None
        self.column = self.source_span.start_column if self.source_span else None
        location = f" at line {self.line}, column {self.column}" if self.source_span else ""
        super().__init__(message + location)


def _type_of(value: Value, node: ast.NodeBase) -> str:
    """Keep bool distinct from number despite Python's bool/int inheritance."""
    if type(value) is bool:
        return "bool"
    if type(value) is int:
        return "number"
    if type(value) is float and math.isfinite(value):
        return "number"
    if type(value) is str:
        return "text"
    raise NovaRuntimeError("Expected a finite number, text, or bool value", node)


def _check_type(value: Value, expected: str, node: ast.NodeBase) -> None:
    actual = _type_of(value, node)
    if actual != expected:
        raise NovaRuntimeError(f"Expected {expected}, got {actual}", node)


@dataclass
class _Binding:
    value: Value
    type_name: str


class _Environment:
    """A lexical scope; assignment updates the nearest existing binding."""

    def __init__(self, parent: _Environment | None = None):
        self.parent = parent
        self.bindings: dict[str, _Binding] = {}

    def declare(self, name: str, value: Value, type_name: str, node: ast.NodeBase) -> None:
        if name in self.bindings:
            raise NovaRuntimeError(f"Variable '{name}' is already declared in this scope", node)
        _check_type(value, type_name, node)
        self.bindings[name] = _Binding(value, type_name)

    def resolve(self, name: str, node: ast.NodeBase) -> _Binding:
        if name in self.bindings:
            return self.bindings[name]
        if self.parent is not None:
            return self.parent.resolve(name, node)
        raise NovaRuntimeError(f"Undefined variable '{name}'", node)


class _ReturnSignal(Exception):
    """Internal control flow that exits all nested blocks of a function."""

    def __init__(self, value: Value):
        self.value = value


class _LoopSignal(Exception):
    """Internal loop control, caught by a loop or stopped at a function boundary."""

    def __init__(self, node: ast.NodeBase):
        self.node = node


class _BreakSignal(_LoopSignal):
    pass


class _ContinueSignal(_LoopSignal):
    pass


class Interpreter:
    """Execute named functions from Python or Nova call expressions."""

    def __init__(self, program: ast.Program):
        self.functions: dict[str, ast.FuncDecl] = {}
        self._depth = 0
        for function in program.functions:
            if function.name == "print":
                raise NovaRuntimeError("Function name 'print' is reserved for console output", function)
            if function.name in self.functions:
                raise NovaRuntimeError(f"Duplicate function '{function.name}'", function)
            names = set()
            for parameter in function.inputs:
                if parameter.name in names:
                    raise NovaRuntimeError(f"Duplicate parameter '{parameter.name}'", parameter)
                names.add(parameter.name)
            self.functions[function.name] = function

    def call(self, name: str, *arguments: Value) -> Value | None:
        """Run a fresh invocation; falling through returns Python None."""
        return self._invoke(name, arguments, None)

    def _invoke(self, name: str, arguments, call_node: ast.CallExpr | None) -> Value | None:
        if name == "print":
            for value in arguments:
                _type_of(value, call_node)
            print(" ".join("true" if value is True else "false" if value is False
                           else str(value) for value in arguments))
            return None
        if name not in self.functions:
            raise NovaRuntimeError(f"Undefined function '{name}'", call_node)
        function = self.functions[name]
        if len(arguments) != len(function.inputs):
            raise NovaRuntimeError(
                f"Function '{name}' expects {len(function.inputs)} arguments, got {len(arguments)}",
                call_node or function,
            )
        environment = _Environment()
        for parameter, value in zip(function.inputs, arguments):
            environment.declare(parameter.name, value, parameter.type_name.name, call_node or parameter)
        if self._depth >= 50:
            raise NovaRuntimeError("Maximum call depth exceeded (50)", call_node or function)
        self._depth += 1
        try:
            try:
                self._execute_block(function.run_block, environment)
            except _ReturnSignal as signal:
                return signal.value
            except _LoopSignal as signal:
                raise NovaRuntimeError("Loop control cannot leave a function or run outside a loop",
                                       signal.node) from None
            except RecursionError as error:
                raise NovaRuntimeError("Interpreter recursion limit exceeded", call_node or function) from error
            return None
        finally:
            self._depth -= 1

    def _execute_block(self, block: ast.BlockStmt, environment: _Environment) -> None:
        for statement in block.statements:
            self._execute(statement, environment)

    def _execute(self, node: ast.Stmt, environment: _Environment) -> None:
        if isinstance(node, ast.ExprStmt):
            self._evaluate_call(node.expression, environment)
        elif isinstance(node, ast.LetStmt):
            value = self._evaluate(node.value, environment)
            type_name = node.declared_type.name if node.declared_type else _type_of(value, node)
            environment.declare(node.name, value, type_name, node)
        elif isinstance(node, ast.AssignStmt):
            binding = environment.resolve(node.target.name, node.target)
            value = self._evaluate(node.value, environment)
            _check_type(value, binding.type_name, node)
            binding.value = value
        elif isinstance(node, ast.BreakStmt):
            raise _BreakSignal(node)
        elif isinstance(node, ast.ContinueStmt):
            raise _ContinueSignal(node)
        elif isinstance(node, ast.ReturnStmt):
            raise _ReturnSignal(self._evaluate(node.value, environment))
        elif isinstance(node, ast.BlockStmt):
            self._execute_block(node, _Environment(environment))
        elif isinstance(node, ast.WhileStmt):
            while True:
                value = self._evaluate(node.condition, environment)
                _check_type(value, "bool", node.condition)
                if not value:
                    break
                try:
                    self._execute_block(node.block, _Environment(environment))
                except _ContinueSignal:
                    continue
                except _BreakSignal:
                    break
        elif isinstance(node, ast.IfStmt):
            branches = [(node.condition, node.then_block)]
            branches.extend((clause.condition, clause.block) for clause in node.else_if_clauses)
            for condition, block in branches:
                value = self._evaluate(condition, environment)
                _check_type(value, "bool", condition)
                if value:
                    self._execute_block(block, _Environment(environment))
                    return
            if node.else_block is not None:
                self._execute_block(node.else_block, _Environment(environment))
        else:
            raise NovaRuntimeError(f"Unsupported statement: {type(node).__name__}", node)

    def _evaluate_call(self, node: ast.CallExpr, environment: _Environment) -> Value | None:
        """Evaluate arguments left to right; calls use a separate function namespace."""
        arguments = [self._evaluate(argument, environment) for argument in node.arguments]
        return self._invoke(node.callee.name, arguments, node)

    def _evaluate(self, node: ast.Expr, environment: _Environment) -> Value:
        if isinstance(node, ast.CallExpr):
            result = self._evaluate_call(node, environment)
            if result is None:
                raise NovaRuntimeError(f"Function '{node.callee.name}' did not return a value", node)
            return result
        if isinstance(node, ast.NumberLiteralExpr):
            _check_type(node.value, "number", node)
            return node.value
        if isinstance(node, ast.TextLiteralExpr):
            _check_type(node.value, "text", node)
            return node.value
        if isinstance(node, ast.BoolLiteralExpr):
            _check_type(node.value, "bool", node)
            return node.value
        if isinstance(node, ast.IdentifierExpr):
            return environment.resolve(node.name, node).value
        if isinstance(node, ast.GroupedExpr):
            return self._evaluate(node.expression, environment)
        if isinstance(node, ast.UnaryExpr):
            value = self._evaluate(node.operand, environment)
            if node.operator == "NOT":
                _check_type(value, "bool", node.operand)
                return not value
            if node.operator == "NEG":
                _check_type(value, "number", node.operand)
                return -value
            raise NovaRuntimeError(f"Unsupported unary operator: {node.operator}", node)
        if isinstance(node, ast.BinaryExpr):
            left = self._evaluate(node.left, environment)
            if node.operator in ("AND", "OR"):
                _check_type(left, "bool", node.left)
                if node.operator == "AND" and not left:
                    return False
                if node.operator == "OR" and left:
                    return True
                right = self._evaluate(node.right, environment)
                _check_type(right, "bool", node.right)
                return right
            right = self._evaluate(node.right, environment)
            left_type, right_type = _type_of(left, node), _type_of(right, node)
            if node.operator in ("EQ", "NE"):
                if left_type != right_type:
                    raise NovaRuntimeError("Equality requires operands of the same type", node)
                return left == right if node.operator == "EQ" else left != right
            if node.operator == "ADD" and left_type == right_type == "text":
                return left + right
            if left_type != "number" or right_type != "number":
                raise NovaRuntimeError(f"Operator {node.operator} requires number operands", node)
            if node.operator == "GE":
                return left >= right
            if node.operator == "LE":
                return left <= right
            if node.operator == "GT":
                return left > right
            if node.operator == "LT":
                return left < right
            try:
                if node.operator == "ADD":
                    result = left + right
                elif node.operator == "SUB":
                    result = left - right
                elif node.operator == "MUL":
                    result = left * right
                elif node.operator == "DIV":
                    if right == 0:
                        raise NovaRuntimeError("Division by zero", node)
                    result = left / right
                else:
                    raise NovaRuntimeError(f"Unsupported operator: {node.operator}", node)
            except OverflowError as error:
                raise NovaRuntimeError("Numeric overflow", node) from error
            _check_type(result, "number", node)
            return result
        raise NovaRuntimeError(f"Unsupported expression: {type(node).__name__}", node)


def run(source: str, function: str = "main", *arguments: Value) -> Value | None:
    """Parse, analyze, and execute one function through the complete pipeline."""
    program = parse(source)
    analyze(program)
    return Interpreter(program).call(function, *arguments)
