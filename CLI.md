# Running Nova files

Save your code in a UTF-8 `.nova` file, then run it from the project directory:

```shell
python nova.py hello.nova
```

Expected output:

```text
Hola desde Nova
```

Requires Python 3.10 or later. No additional packages are needed. If `python`
is not on PATH, use the full path to your Python executable instead.

The CLI reads the file, invokes the lexer and parser, and executes `main`
without arguments. Define `func main:` with a `run` block and no `inputs`.
Other functions may be present but are not automatically executed.

The CLI displays the returned value. Text is printed without quotes and booleans
as `true` or `false`. A function that reaches its end without returning prints
nothing. A numeric return value is output, not the process exit status.

```shell
python nova.py --help
python nova.py "path with spaces/program.nova"
python -m unittest discover -v
```

Relative source paths are resolved from the terminal's current directory.
The script itself can also be invoked by its full path from another directory.
UTF-8 files with or without a byte-order mark are accepted.

Exit codes: 0 for success, 1 for file or language errors, and 2 for invalid
command-line usage. Diagnostics go to stderr and include the file, line,
column, and a source pointer when available. Returned values go to stdout.

This first CLI does not install a global `nova` command or add editor syntax
highlighting. It runs the currently implemented Nova language unchanged.
