"""Calculations and unit conversion (safe eval, stdlib only)."""

import ast
import operator
import re

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}

_CONV = {
    ("miles", "km"): 1.60934, ("mile", "km"): 1.60934,
    ("km", "miles"): 0.621371, ("km", "mile"): 0.621371,
    ("meters", "feet"): 3.28084, ("meter", "feet"): 3.28084, ("m", "ft"): 3.28084,
    ("feet", "meters"): 0.3048, ("foot", "meters"): 0.3048, ("ft", "m"): 0.3048,
    ("kg", "lb"): 2.20462, ("kilos", "pounds"): 2.20462,
    ("lb", "kg"): 0.453592, ("pounds", "kilos"): 0.453592,
    ("celsius", "fahrenheit"): None, ("c", "f"): None,
    ("fahrenheit", "celsius"): None, ("f", "c"): None,
    ("inches", "cm"): 2.54, ("inch", "cm"): 2.54, ("in", "cm"): 2.54,
    ("cm", "inches"): 0.393701, ("cm", "inch"): 0.393701,
}


def _safe_eval(expr):
    node = ast.parse(expr, mode="eval")

    def _ev(n):
        if isinstance(n, ast.Expression):
            return _ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](_ev(n.left), _ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](_ev(n.operand))
        raise ValueError("unsupported expression")

    return _ev(node)


def _fmt(n):
    if isinstance(n, float) and n.is_integer():
        return str(int(n))
    return f"{n:.4g}"


def _spoken_to_symbols(expr):
    """Turn worded sums into operators: '5 times 6' -> '5 * 6'.

    Without this, any spoken sum kept letters, failed the symbol-only
    fullmatch below, and returned None -- so the question fell through to the
    wikipedia skill, which fuzzy-matched an unrelated article ('what is 5
    times 6' came back as a rifle cartridge). Only expressions that end up
    purely numeric are ever evaluated, so over-replacing is harmless.
    """
    e = expr
    e = re.sub(r"(?<=\d)\s*[x×]\s*(?=\d)", "*", e)          # 5 x 6
    e = re.sub(r"(?<=\d)\s+and\s+(?=\d)", "+", e)            # 8 and 7
    e = re.sub(r"\b(?:times|multiplied by|multiply by|multiply)\b", "*", e)
    e = re.sub(r"\b(?:plus|added to)\b", "+", e)
    e = re.sub(r"\b(?:minus|subtracted from|subtract)\b", "-", e)
    e = re.sub(r"\b(?:divided by|divide by|over)\b", "/", e)
    e = re.sub(r"\b(?:to the power of|raised to)\b", "**", e)
    e = re.sub(r"\b(?:the\s+)?(?:sum|difference|product|quotient)\s+(?:of|between)\b", "", e)
    return re.sub(r"\s+", " ", e).strip()


def handler(text, ctx):
    lower = text.lower().strip()

    # percent: "15% of 200"
    m = re.match(r"^(?:what is\s+)?([\d.]+)\s*%\s+of\s+([\d.]+)\s*\??$", lower)
    if m:
        try:
            return f"{m.group(1)}% of {m.group(2)} = {_fmt(float(m.group(1)) / 100 * float(m.group(2)))}"
        except ValueError:
            return None

    # conversion: "convert 10 miles to km"
    m = re.match(r"^(?:convert|how many)\s+([\d.]+)\s*([a-z°]+)\s+(?:to|in)\s+([a-z°]+)\s*\??$", lower)
    if m:
        try:
            val = float(m.group(1))
        except ValueError:
            return None
        frm, to = m.group(2), m.group(3)
        key = (frm, to)
        if key in _CONV:
            f = _CONV[key]
            if f is None:
                if frm.startswith("c"):
                    return f"{_fmt(val)}C = {_fmt(val * 9 / 5 + 32)}F"
                return f"{_fmt(val)}F = {_fmt((val - 32) * 5 / 9)}C"
            return f"{_fmt(val)} {frm} = {_fmt(val * f)} {to}"
        return None

    # arithmetic: "what is 2 + 2", "what is 5 times 6", "calculate (3+4)*2"
    m = re.match(r"^(?:what is|whats|calculate|compute|solve|math|maths?)\s+(.+?)\s*\??$", lower)
    if not m:
        m = re.match(r"^(?:the\s+)?(?:sum|difference|product|quotient)\s+(?:of|between)\s+(.+?)\s*\??$", lower)
    expr = None
    if m:
        expr = _spoken_to_symbols(m.group(1))
    elif re.fullmatch(r"[\d\s+\-*/().%^]+", lower) and re.search(r"\d", lower):
        expr = lower
    if expr:
        expr = expr.replace("^", "**").replace("%", "/100").strip()
        if re.fullmatch(r"[\d\s+\-*/().]+", expr):
            try:
                return f"{_fmt(_safe_eval(expr))}"
            except (ValueError, SyntaxError, ZeroDivisionError, OverflowError):
                return None
    return None
