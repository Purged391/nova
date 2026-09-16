"""Exercise the CLI as a real subprocess, including paths and exit codes."""

from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest


CLI = Path(__file__).with_name("nova.py")


class CLITests(unittest.TestCase):
    def invoke(self, *arguments, cwd=None):
        environment = dict(os.environ, PYTHONIOENCODING="utf-8")
        return subprocess.run([sys.executable, str(CLI), *map(str, arguments)],
                              cwd=cwd, env=environment, capture_output=True,
                              text=True, encoding="utf-8", timeout=10)

    def execute(self, source, encoding="utf-8"):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hello world.nova"
            path.write_text(source, encoding=encoding)
            return self.invoke(path.name, cwd=directory)

    def test_hello_and_bom(self):
        for encoding in ("utf-8", "utf-8-sig"):
            result = self.execute('func main:\n    run:\n        return "Hola, ñ"', encoding)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "Hola, ñ\n")
            self.assertEqual(result.stderr, "")

    def test_result_display(self):
        for statement, output in [("return 7", "7\n"), ("return false", "false\n"),
                                  ("let x = 1", "")]:
            result = self.execute("func main:\n    run:\n        " + statement)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, output)

    def test_language_diagnostics(self):
        for statement, error in [("return @", "LexerError"), ("let x 1", "ParseError"),
                                 ("return 1 / 0", "NovaRuntimeError")]:
            result = self.execute("func main:\n    run:\n        " + statement)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn(error, result.stderr)
            self.assertIn("hello world.nova:3:", result.stderr)
            self.assertIn("^", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_entry_point_errors(self):
        for source in ['func other:\n    run:\n        return 1',
                       'func main:\n    inputs x: number\n    run:\n        return x']:
            result = self.execute(source)
            self.assertEqual(result.returncode, 1)
            self.assertIn("NovaRuntimeError", result.stderr)

    def test_file_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.nova"
            result = self.invoke(path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("File error", result.stderr)
            path.write_bytes(b"\xff")
            result = self.invoke(path)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("Traceback", result.stderr)

    def test_help_and_usage(self):
        self.assertEqual(self.invoke("--help").returncode, 0)
        self.assertEqual(self.invoke().returncode, 2)
        self.assertEqual(self.invoke("--unknown").returncode, 2)


if __name__ == "__main__":
    unittest.main()
