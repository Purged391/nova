"""Build a function that declares x = 2 + 3 and returns x."""

import json

from ast_nodes import (
    BinaryExpr, BlockStmt, FuncDecl, IdentifierExpr, LetStmt,
    NumberLiteralExpr, Program, ReturnStmt, TypeRef,
)


def main() -> None:
    program = Program(functions=[
        FuncDecl(
            name="main",
            inputs=[],
            run_block=BlockStmt(statements=[
                LetStmt(
                    name="x",
                    declared_type=TypeRef(name="number"),
                    value=BinaryExpr(
                        left=NumberLiteralExpr(value=2),
                        operator="ADD",
                        right=NumberLiteralExpr(value=3),
                    ),
                ),
                ReturnStmt(value=IdentifierExpr(name="x")),
            ]),
        ),
    ])
    print(json.dumps(program.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

