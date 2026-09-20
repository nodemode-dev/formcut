import ast
import math
import operator

FUNCTIONS = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "abs": abs,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
    "floor": math.floor,
    "ceil": math.ceil,
}
OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Mod: operator.mod}


def evaluate(expression: str, time: float, duration: float, value: float) -> float:
    if len(expression) > 512:
        raise ValueError("Expression is too long")
    root = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(root)) > 100:
        raise ValueError("Expression is too complex")
    variables = {"t": time, "duration": duration, "value": value, "pi": math.pi}

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id in variables:
            return variables[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
            return OPERATORS[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in FUNCTIONS
            and not node.keywords
            and len(node.args) <= 4
        ):
            return FUNCTIONS[node.func.id](*(visit(arg) for arg in node.args))
        raise ValueError("Only arithmetic, t, duration, value and named math functions are allowed")

    result = float(visit(root))
    if not math.isfinite(result) or abs(result) > 1e6:
        raise ValueError("Expression result is outside the supported range")
    return result
