"""AST nodes for Nova v0.1. Requires Python 3.10 or later.

Type annotations describe types; they do not validate values at runtime.
Use to_dict() to export: it omits source_span when unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Literal, TypeAlias


TypeName: TypeAlias = Literal["number", "text", "bool"]
BinaryOperator: TypeAlias = Literal["ADD", "SUB", "MUL", "DIV", "GT", "LT", "EQ"]


@dataclass
class SourceSpan:
    """Source position with one-based lines and columns and an exclusive end."""

    start_line: int
    start_column: int
    end_line: int
    end_column: int


@dataclass(kw_only=True)
class NodeBase:
    """Shared metadata. source_span must always be passed by keyword."""

    source_span: SourceSpan | None = None

    def to_dict(self) -> dict:
        """Convert the tree to a JSON-serializable dictionary."""
        return {
            item.name: _to_value(getattr(self, item.name))
            for item in fields(self)
            if item.name != "source_span" or self.source_span is not None
        }


@dataclass
class TypeRef(NodeBase):
    name: TypeName
    type: Literal["TypeRef"] = field(default="TypeRef", init=False)


@dataclass
class InputParam(NodeBase):
    name: str
    type_name: TypeRef
    type: Literal["InputParam"] = field(default="InputParam", init=False)


@dataclass
class Program(NodeBase):
    functions: list[FuncDecl]
    type: Literal["Program"] = field(default="Program", init=False)


@dataclass
class FuncDecl(NodeBase):
    name: str
    inputs: list[InputParam]
    run_block: BlockStmt
    type: Literal["FuncDecl"] = field(default="FuncDecl", init=False)


@dataclass
class BlockStmt(NodeBase):
    statements: list[Stmt]
    type: Literal["BlockStmt"] = field(default="BlockStmt", init=False)


@dataclass
class LetStmt(NodeBase):
    name: str
    declared_type: TypeRef | None
    value: Expr
    type: Literal["LetStmt"] = field(default="LetStmt", init=False)


@dataclass
class AssignStmt(NodeBase):
    target: IdentifierExpr
    value: Expr
    type: Literal["AssignStmt"] = field(default="AssignStmt", init=False)


@dataclass
class ElseIfClause(NodeBase):
    condition: Expr
    block: BlockStmt
    type: Literal["ElseIfClause"] = field(default="ElseIfClause", init=False)


@dataclass
class IfStmt(NodeBase):
    condition: Expr
    then_block: BlockStmt
    else_if_clauses: list[ElseIfClause]
    else_block: BlockStmt | None
    type: Literal["IfStmt"] = field(default="IfStmt", init=False)


@dataclass
class ReturnStmt(NodeBase):
    value: Expr
    type: Literal["ReturnStmt"] = field(default="ReturnStmt", init=False)


@dataclass
class IdentifierExpr(NodeBase):
    name: str
    type: Literal["IdentifierExpr"] = field(default="IdentifierExpr", init=False)


@dataclass
class NumberLiteralExpr(NodeBase):
    value: int | float
    type: Literal["NumberLiteralExpr"] = field(default="NumberLiteralExpr", init=False)


@dataclass
class TextLiteralExpr(NodeBase):
    value: str
    type: Literal["TextLiteralExpr"] = field(default="TextLiteralExpr", init=False)


@dataclass
class BoolLiteralExpr(NodeBase):
    value: bool
    type: Literal["BoolLiteralExpr"] = field(default="BoolLiteralExpr", init=False)


@dataclass
class BinaryExpr(NodeBase):
    left: Expr
    operator: BinaryOperator
    right: Expr
    type: Literal["BinaryExpr"] = field(default="BinaryExpr", init=False)


@dataclass
class GroupedExpr(NodeBase):
    expression: Expr
    type: Literal["GroupedExpr"] = field(default="GroupedExpr", init=False)


@dataclass
class CallExpr(NodeBase):
    """Call a named function with positional arguments."""

    callee: IdentifierExpr
    arguments: list[Expr]
    type: Literal["CallExpr"] = field(default="CallExpr", init=False)


@dataclass
class ExprStmt(NodeBase):
    """Execute a call for its effects and discard its result."""

    expression: CallExpr
    type: Literal["ExprStmt"] = field(default="ExprStmt", init=False)


@dataclass
class WhileStmt(NodeBase):
    """Repeat a block while its condition evaluates to true."""

    condition: Expr
    block: BlockStmt
    type: Literal["WhileStmt"] = field(default="WhileStmt", init=False)


@dataclass
class BreakStmt(NodeBase):
    """Exit the nearest enclosing loop."""

    type: Literal["BreakStmt"] = field(default="BreakStmt", init=False)


@dataclass
class ContinueStmt(NodeBase):
    """Start the next iteration of the nearest enclosing loop."""

    type: Literal["ContinueStmt"] = field(default="ContinueStmt", init=False)


Stmt: TypeAlias = BlockStmt | LetStmt | AssignStmt | IfStmt | ReturnStmt | ExprStmt | WhileStmt | BreakStmt | ContinueStmt
Expr: TypeAlias = (
    IdentifierExpr | NumberLiteralExpr | TextLiteralExpr
    | BoolLiteralExpr | BinaryExpr | GroupedExpr | CallExpr
)


def _to_value(value: object) -> object:
    if isinstance(value, NodeBase):
        return value.to_dict()
    if isinstance(value, SourceSpan):
        return {item.name: getattr(value, item.name) for item in fields(value)}
    if isinstance(value, list):
        return [_to_value(item) for item in value]
    return value

