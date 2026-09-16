# Nova parser v0.1

The recursive-descent parser consumes lexer tokens and creates the dataclasses
in `ast_nodes.py`. It does not execute code or check variable and return types.
All parser-created nodes include one-based, exclusive-end source spans.
Block spans cover their first through last statements, excluding indentation.

Run `python example_parser.py` to print the AST of the two function examples.
Run `python -m unittest discover -v` to run the lexer and parser tests.
Python 3.10 or later is required. No third-party packages are needed.

```python
from parser import parse

program = parse('func sayHello:\n    run:\n        return "Hola"\n')
data = program.to_dict()
```

## Grammar

Brackets indicate optional parts; braces indicate repetition.

```text
program      = { function } EOF
function     = "func" IDENTIFIER ":" NEWLINE INDENT
               [ "inputs" parameter { "," parameter } NEWLINE ]
               "run" block DEDENT
parameter    = IDENTIFIER ":" type
type         = "number" | "text" | "bool"
block        = ":" NEWLINE INDENT statement { statement } DEDENT
statement    = let | assignment | return | conditional | call NEWLINE
let          = "let" IDENTIFIER [ ":" type ] "=" expression NEWLINE
assignment   = IDENTIFIER "=" expression NEWLINE
return       = "return" expression NEWLINE
conditional  = "if" expression block
               { "else" "if" expression block } [ "else" block ]
expression   = comparison { "==" comparison }
comparison   = addition { ( ">" | "<" ) addition }
addition     = product { ( "+" | "-" ) product }
product      = primary { ( "*" | "/" ) primary }
call         = IDENTIFIER "(" [ expression { "," expression } ] ")"
primary      = call | IDENTIFIER | NUMBER | TEXT | "true" | "false"
             | "(" expression ")"
```

Each function has exactly one `run` block and at most one preceding `inputs`
line. Omit that line for zero parameters; empty lists and trailing commas are
not accepted. Blocks must contain at least one statement.

Operators at each precedence level associate to the left. Comparisons are
ordinary binary nodes, not Python-style chained comparisons. Parentheses are
preserved as `GroupedExpr` nodes. Named calls use CallExpr; standalone calls use ExprStmt. Unary operators are not
supported by the current AST. Return type declarations remain deferred.

`ParseError` reports the first syntax error and exposes `line`, `column`, and
`token`. Lexical errors still raise `LexerError`. Duplicate names, undefined
variables, operand types, and return-path checks belong to future semantic
analysis; successfully parsing a program does not guarantee it can execute.
