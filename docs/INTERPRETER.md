# Nova interpreter v0.1

The tree-walking interpreter executes the dataclasses produced by the parser.
It evaluates expressions recursively and executes statements in source order.
It never uses Python `eval` or `exec` to execute Nova source.

```python
from interpreter import Interpreter, run
from parser import parse

source = '''func sum:
    inputs a: number, b: number
    run:
        return a + b
'''

runtime = Interpreter(parse(source))
result = runtime.call("sum", 2, 3)  # 5
result = run(source, "sum", 2, 3)   # Equivalent one-shot execution
```

Run `python -m examples.example_interpreter` for the sum and greeting examples.
Run `python -m unittest discover -v` for all tests. Requires Python 3.10+;
no third-party packages are needed.

## Initial runtime rules

These rules make the first implementation executable and can be revised as
the language design develops. They are runtime checks, not a static type system.

- Each call receives positional arguments matching `inputs` in count and type.
  Functions and parameters must have unique names within their respective scopes.
- Values are `number`, `text`, or `bool`; no implicit conversions occur.
  Python booleans do not count as Nova numbers.
- Numbers use Python integers and finite floating-point values. Division uses
  true division (`5 / 2` is `2.5`). Division by zero, floating-point overflow,
  and nonfinite arguments raise runtime errors. Decimal arithmetic therefore
  has ordinary binary floating-point rounding; this is not a final numeric model.
- `let` creates a mutable binding. An omitted type is inferred from its initial
  value and retained on assignment. Duplicate declarations in one scope fail.
- Parameters and the top-level `run` body share a scope. Each executed nested
  block creates a child scope. Inner declarations may shadow outer names;
  assignment updates the nearest existing declaration. Names cannot leak out
  of inner blocks, and each invocation has fresh local state.
- Arithmetic and ordering operators require numbers. `+` also concatenates two
  text values. Equality requires matching types; integers and floats both have
  type `number`. Conditions must be `bool`.
- Only the selected conditional branch executes. Expressions evaluate operands
  from left to right. `return` immediately exits the entire function, including
  nested blocks. Return types remain undeclared and unchecked across branches.
- Reaching the end without returning yields Python `None` to the host API.
  This does not introduce a `null` literal or a new type into Nova.
- Functions can be called from Python or Nova, including forward references and
  recursion. Named calls resolve in the function namespace, independently of variables.
  Async/concurrent execution remains future work.
- Built-in `print(...)` accepts zero or more values, separates them with spaces,
  and ends with a newline. Booleans display as `true`/`false`. It has no return
  value, and its function name cannot be redefined.
- A standalone call discards its result. A call used as an expression must return
  a value; using print or a fallthrough function as a value raises a runtime error
  after its effects execute. No null type is introduced.
- Calls evaluate arguments left to right and use fresh local scopes. The current
  implementation limits active function calls to 50 and reports recursion errors.
- The CLI still displays a returned main value after any explicit console output.

`NovaRuntimeError` provides `source_span`, `line`, and `column` when a source
node exists. Host errors such as an unknown function have no source position.
The loader rejects duplicate function/parameter names. Other checks occur
when statements execute; unreachable code is not type-checked ahead of time.

## While loops

`while condition:` evaluates its condition before every iteration, including
the first. The condition must be bool. A false condition skips the body.
Each iteration has a fresh child scope: local declarations do not leak or
persist between iterations, while assignments can update outer variables.
`return` inside a loop exits the entire function. Loops can be nested and
their conditions may call functions. There is no iteration limit; the body
must eventually make the condition false unless the function returns.
`break`, `continue`, and `while ... else` are not supported yet.

Run `python nova.py examples/while_example.nova` for a three-iteration example.
