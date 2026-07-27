import math
def execute(expression: str, _pet=None) -> str:
    safe = {"abs": abs, "round": round, "int": int, "pi": math.pi, "e": math.e,
            "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
            "floor": math.floor, "ceil": math.ceil, "pow": pow}
    try:
        r = eval(expression, {"__builtins__": {}}, safe)
        return f"{expression} = {r}"
    except Exception as e:
        return f"计算失败: {e}"
