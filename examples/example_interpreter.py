"""Execute Nova functions through the lexer, parser, and interpreter."""

from examples.example_parser import SOURCE
from interpreter import Interpreter
from parser import parse


if __name__ == "__main__":
    interpreter = Interpreter(parse(SOURCE))
    print("sum(2, 3) =", interpreter.call("sum", 2, 3))
    print("sayHello() =", interpreter.call("sayHello"))
