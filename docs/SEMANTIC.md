# Semantic analyzer

`semantic.py` validates a parsed AST without executing any program code.
`analyze(program)` returns `AnalysisResult`, or raises `SemanticError` at the
first detected problem. Its `line`, `column`, and `source_span` support CLI
diagnostics. Analysis does not modify the AST and does not require `main`.

```python
from parser import parse
from semantic import analyze

program = parse('func main:\n    run:\n        return 2 + 3')
result = analyze(program)
assert result.return_types['main'] == 'number'
```

```shell
python nova.py --check examples/calls.nova
python nova.py examples/calls.nova
```

The first command validates only; the second validates and then executes.
`interpreter.run(source, ...)` also analyzes before execution. The low-level
`Interpreter(program)` API deliberately retains direct AST execution so runtime
checks can be tested independently. Call `analyze(program)` before that API if
you want static validation. The existing runtime tests use a helper for this;
semantic tests exercise both analysis and the normal source execution pipeline.

## Checks

- Duplicate function and parameter names; redefinition of the built-in `print`.
- Variables used before declaration, out of scope, or redeclared in one scope.
- Assignment compatibility with explicit or known inferred variable types.
- Function existence, argument counts, and known argument types.
- Operand compatibility, including boolean-only conditions and logical operators.
- Known no-value calls used as expressions.
- Loop control context for ASTs supplied directly to the analyzer.

All function names are collected before bodies are checked, allowing forward
calls and recursion. Local scopes are analyzed in source order. Nested scopes
inherit lookup but not declarations. Types of bindings are not changed by
assignments or merged across branches; an unknown inferred binding remains
unknown until a later analysis pass learns more about its initializer.

## Return summaries

The analyzer propagates function return summaries across repeated passes until
stable, bounded by the number of functions plus two. Each pass uses summaries
from the previous pass, so declaration order does not determine inference.

- `number`, `text`, `bool`: all structural exits return one consistent type.
- `void`: no return statements were found. This is internal metadata only.
- `unknown`: mixed types, uncertain exits, or insufficient information.

An if statement guarantees a return only when every branch, including an else,
returns. Loops are treated as possibly executing zero times. Conditions are not
constant-folded. Unreachable return statements are included conservatively in
type summaries, so some valid programs retain an unknown summary.

Arithmetic can establish a result type even when an operand's type is unknown:
for example, multiplication produces a number if it succeeds. Runtime checks
still enforce the operand requirements. This allows some recursive functions
to infer a return type. Unconstrained recursive cycles can remain unknown.

Unknown values are permitted where a known type is expected, subject to runtime
checking. Mixed return types are not rejected in this first version. Functions
with uncertain fallthrough can be used as values; if they actually fall through,
the interpreter raises an error. A successful check is therefore not a proof of
full type safety, successful termination, or freedom from runtime errors.

## Static checking versus short-circuit execution

`true or missing()` is rejected because `missing` is undefined, even though the
right operand would not run. `false and 1` is rejected because `and` requires
booleans. Conversely, `false and 10 / 0 > 2` passes static analysis: the operand
types are valid, and runtime short-circuiting prevents the division.

Checks also cover unused functions, `if false` bodies, and statements after a
return. Programs that previously hid name or known type errors in unreachable
code now fail before any output. This is the intended behavior change.
