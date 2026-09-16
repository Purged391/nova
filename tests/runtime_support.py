"""Execute parsed ASTs directly to test runtime checks independently of analysis."""

from interpreter import Interpreter
from parser import parse


def run(source, function="main", *arguments):
    return Interpreter(parse(source)).call(function, *arguments)
