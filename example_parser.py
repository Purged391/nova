"""Parse two Nova functions and print their AST as JSON."""

import json

from parser import parse


SOURCE = '''func sum:
    inputs a: number, b: number
    run:
        let result: number = a + b
        return result

func sayHello:
    run:
        return "Hola"
'''


if __name__ == "__main__":
    print(json.dumps(parse(SOURCE).to_dict(), indent=2, ensure_ascii=False))
