"""Command-line entry point for running Nova source files."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from interpreter import NovaRuntimeError, run
from lexer import LexerError
from parser import ParseError, parse
from semantic import SemanticError, analyze


def _report_error(path: Path, source: str, error: Exception) -> None:
    """Print a diagnostic and underline its source position when available."""
    line = getattr(error, "line", None)
    column = getattr(error, "column", None)
    location = f"{path}:{line}:{column}" if line is not None else str(path)
    print(f"{location}: {type(error).__name__}: {error}", file=sys.stderr)
    lines = source.splitlines()
    if line is not None and column is not None and 1 <= line <= len(lines):
        text = lines[line - 1]
        print(f"    {text.expandtabs(4)}", file=sys.stderr)
        prefix = text[:column - 1].expandtabs(4)
        print("    " + " " * len(prefix) + "^", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    """Run main with no arguments; return a process exit status."""
    argument_parser = argparse.ArgumentParser(
        description="Run a Nova file by calling its main function.",
    )
    argument_parser.add_argument("file", type=Path, help="Path to a UTF-8 Nova source file")
    argument_parser.add_argument("--check", action="store_true",
                                 help="Check syntax and semantics without executing the file")
    args = argument_parser.parse_args(argv)
    try:
        source = args.file.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        print(f"{args.file}: File error: {error}", file=sys.stderr)
        return 1
    try:
        if args.check:
            analyze(parse(source))
            print("Check passed")
            return 0
        result = run(source)
    except (LexerError, ParseError, SemanticError, NovaRuntimeError) as error:
        _report_error(args.file, source, error)
        return 1
    if result is not None:
        if type(result) is bool:
            print("true" if result else "false")
        else:
            print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
