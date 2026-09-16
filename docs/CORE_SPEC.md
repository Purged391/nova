# Nova core specification — v0.1

This document records the implemented core language. It distinguishes current
rules from unresolved design choices; it is not a commitment to future features.
The detailed grammar is in [PARSER.md](PARSER.md). The serialized AST structure
is defined by [ast_nova.json](../schemas/ast_nova.json).

## 1. Source and structure

Source files use UTF-8. Identifiers are case-sensitive and match
`[A-Za-z_][A-Za-z0-9_]*`. Comments begin with `#` outside strings.
Blocks use spaces for indentation. Increased indentation opens a block;
dedentation must match an earlier level. Four spaces is the recommended style.
Blank and comment-only lines do not affect indentation. Tabs outside strings
and comments are rejected. Parentheses allow multiline expressions.

A file contains zero or more named functions. Each function has an optional,
nonempty comma-separated `inputs` list followed by exactly one `run` block.
Each input has an explicit primitive type. Blocks contain at least one statement.

```text
func sum:
    inputs a: number, b: number
    run:
        let result = a + b
        return result
```

Trailing commas, nested function declarations, imports, and declared return
types are not supported. The CLI invokes `main` without arguments; a file
checked with `--check` does not need an entry point.

## 2. Values and bindings

The primitive types are `number`, `text`, and `bool`. No implicit conversions
occur. Booleans are distinct from numbers. There is no null value in Nova source.

- `number`: integers and decimal literals. Integers use the host's integer
  representation; decimals and division use finite binary floating-point values.
  Division by zero and numeric overflow are runtime errors. Exponent notation
  is not accepted. A leading minus is a unary operation, not part of a literal.
- `text`: Unicode text in double quotes. Supported escapes are `\n`, `\r`,
  `\t`, `\"`, and `\\`. Physical multiline string literals are not supported.
- `bool`: `true` or `false`.

`let name [: type] = expression` declares a mutable binding. Its type is the
annotation, or the type of its initial value. Later assignment cannot change
that type. Static inference can be unknown; runtime binding types are still
established by their initial values and enforced on every assignment.

A name must be declared before use within its scope. Duplicate declarations
in one scope are errors. The initializer is resolved before the new declaration,
so an inner `let x = x` can read an outer `x`. Without an outer binding it fails.

## 3. Scope

Parameters and a function's `run` block share one scope. Nested blocks create
child scopes and may shadow outer names. Assignment updates the nearest existing
binding. Block-local declarations do not escape the block. Each loop iteration
creates a fresh child scope. Each function call has fresh local bindings and
cannot read the caller's local variables.

Function names occupy a separate namespace. All functions in a file are available
to calls regardless of declaration order. Duplicate function names and duplicate
parameter names are rejected. The built-in function name `print` cannot be
redefined as a function; a variable of that name does not change call resolution.

## 4. Expressions

Precedence, from weakest to strongest:

| Level | Operators |
| --- | --- |
| 1 | `or` |
| 2 | `and` |
| 3 | `not` |
| 4 | `==`, `!=` |
| 5 | `<`, `>`, `<=`, `>=` |
| 6 | `+`, `-` |
| 7 | `*`, `/` |
| 8 | Unary `-` |
| 9 | Named calls, literals, names, parenthesized expressions |

Binary operators at one level associate to the left. Unary operators associate
to the right. `not x == y` means `not (x == y)`. Comparisons are binary operations,
not comparison chains; write `a < b and b < c` to combine two comparisons.

Arithmetic and ordering require numbers. `+` additionally concatenates two text
values. Equality and inequality require matching types; integers and decimals
both have type `number`. Unary minus requires a number.

Logical operators require booleans and return booleans. Evaluation is left to
right. `and` skips its right operand when the left is false; `or` skips its right
operand when the left is true. Static analysis still checks both operands for
known errors. It does not execute them, including any function calls.

## 5. Functions and output

Calls use `name(arg1, arg2)` with positional arguments evaluated left to right.
User functions require matching argument counts and types. Calls may appear
inside expressions or as standalone statements that discard their results.
Functions are not first-class values; calling arbitrary expressions is unsupported.

`return expression` immediately exits the entire function, including all nested
loops and conditionals. A function may fall through without a return. The Python
API receives `None` in that case, but a Nova expression cannot use a missing value.
Functions may currently return different primitive types along different paths.
Declared return types and a policy for such mixed returns remain unresolved.

`print(...)` accepts any number of primitive values, separates them with spaces,
and ends with a newline. Booleans display as `true` and `false`. `print()` emits
an empty line. It does not return a value. Static analysis rejects its use where
a value is required. The CLI also displays a returned `main` value after output.

## 6. Control flow

`if`, `else if`, and `else` select the first applicable branch. Conditions must
be boolean. `while condition:` tests the condition before every iteration,
including the first. There is no iteration limit.

`break` exits the nearest enclosing loop. `continue` rechecks that loop's condition
and skips the remaining statements of the current iteration. Neither takes an
argument or label. Both must occur inside a loop in the same function, even in
unreachable source. They cannot affect a caller's loop. `while ... else` is absent.

## 7. Validation and execution

The public execution pipeline is source → tokens → AST → semantic analysis →
interpreter. Lexical, syntax, and known semantic errors stop execution before
any Nova instruction runs. The current diagnostic API reports the first error
with its source position when available.

Semantic analysis visits all functions, all branches, both logical operands,
and statements after a return. It checks names, scopes, declarations, calls,
known operand types, assignments, and boolean conditions. It does not perform
constant evaluation. Division by zero, overflow, host argument validation,
unknown-type operations, missing values on uncertain return paths, and recursion
limits remain runtime concerns.

Return inference is conservative: a function with no return statements has no
value; a function whose structural paths all return the same known type receives
that type summary. Other cases may remain unknown. See [SEMANTIC.md](SEMANTIC.md).
Unknown is analysis metadata, not an assignable Nova type or a promise of safety.

## 8. Implementation limits and future decisions

The current interpreter uses Python, caps active user-function calls at 50,
and can encounter host resource limits. These are implementation limits, not
the final execution or numeric model of Nova.

Still unresolved: declared/inferred return-type policy, exhaustive return checks,
the complete static type system, exact portable numeric representation, modules,
collections, structured data, recoverable language errors, async/concurrency,
memory management, bytecode, and native compilation.
