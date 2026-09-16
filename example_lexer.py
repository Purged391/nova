"""Print the tokens of a small Nova function."""

from lexer import Lexer


SOURCE = '''func main:
    run:
        let x: number = 2 + 3
        if x == 5:
            return "Hello, Nova!"
        else:
            return "Unexpected result"
'''


if __name__ == "__main__":
    for token in Lexer(SOURCE).tokenize():
        span = token.source_span
        print(f"{span.start_line}:{span.start_column} "
              f"{token.kind.name:14} {token.lexeme!r} value={token.value!r}")
