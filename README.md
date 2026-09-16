# Nova

A small programming language implemented in Python. Requires Python 3.10 or
later and no third-party packages.

## Run a program

From the project root:

```shell
python nova.py examples/hello.nova
python nova.py examples/calls.nova
python nova.py examples/while_example.nova
```

You can save your own `.nova` files anywhere and pass their paths to the CLI.

## Project layout

```text
nova.py          Command-line entry point
lexer.py         Source text to tokens
parser.py        Tokens to AST
ast_nodes.py     AST dataclasses
interpreter.py   AST execution
examples/       Nova programs and Python demonstrations
tests/          Automated tests
docs/           Language and implementation documentation
schemas/        JSON Schema for the AST
```

## Development

Run all tests from the project root:

```shell
python -m unittest discover -v
```

Run Python demonstrations as modules so imports resolve from the project root:

```shell
python -m examples.example_ast
python -m examples.example_lexer
python -m examples.example_parser
python -m examples.example_interpreter
```

## Documentation

- [CLI usage](docs/CLI.md)
- [Lexer rules](docs/LEXER.md)
- [Parser grammar](docs/PARSER.md)
- [Interpreter semantics](docs/INTERPRETER.md)
- [AST schema](schemas/ast_nova.json)
