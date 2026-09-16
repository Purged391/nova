# Nova lexer v0.1

The lexer converts source text into tokens. The parser will consume these tokens
to build the AST; the interpreter will eventually execute that AST.

Run the example with `python -m examples.example_lexer` and the tests with
`python -m unittest discover -v` from the project root. Python 3.10+ is required.

Each token stores its kind, original spelling (`lexeme`), decoded literal value,
and source span. Lines and columns start at 1; end positions are exclusive.
Columns count Unicode code points. Synthetic tokens have empty lexemes.

## Current lexical rules

- Keywords: `func`, `inputs`, `run`, `let`, `if`, `while`, `break`, `continue`, `and`, `or`, `not`, `else`, `return`,
  `number`, `text`, `bool`, `true`, and `false`. Names are case-sensitive.
- Identifiers follow `[A-Za-z_][A-Za-z0-9_]*`, matching the AST schema.
- Numbers are integers or decimals with digits on both sides of the decimal
  point. Exponent notation is not supported. Minus is a separate token;
  the parser distinguishes subtraction from unary negation.
- Strings use double quotes and support Unicode text and the escapes
  `\n`, `\r`, `\t`, `\"`, and `\\`. Physical multiline strings are not supported.
- Comments start with `#` and continue to the end of the line.
- Operators: `+`, `-`, `*`, `/`, `>`, `<`, `==`, `!=`, `<=`, `>=`, `and`, `or`, `not`; assignment uses `=`.
- Punctuation: `(`, `)`, `:`, and `,`.
- Indentation uses spaces. Any increased width starts a level; dedentation must
  match an earlier level. Four spaces per level is the recommended style.
  Tabs outside strings and comments are rejected.
- Blank and comment-only lines do not affect block structure. Newlines inside
  parentheses are ignored. LF, CRLF, and CR are supported.
- A final logical `NEWLINE` is inserted when needed. Remaining blocks close
  with `DEDENT` tokens, followed by `EOF`.

The lexer does not decide whether a block is legal after a particular statement,
whether a variable exists, or whether an operation has compatible types.
Those checks belong to the parser and semantic analysis.

Functions may declare a comma-separated parameter list, for example
`inputs a: number, b: number`, before their `run` block. The `inputs` line
may be omitted for functions without parameters. The parser will enforce these rules.

