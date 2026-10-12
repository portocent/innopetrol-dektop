"""Safe curve calculator.

Evaluates expressions such as `(2.65 - RHOB) / (2.65 - 1.0)` on numpy arrays.
It does NOT use `eval()`: the expression is parsed with the `ast` module and only numbers,
curve names, arithmetic/comparison operators and a closed list of functions are allowed.
Anything else (attributes, imports, lambdas, subscripts…) is rejected.
"""

from __future__ import annotations

import ast
import operator
import re

import numpy as np

from innopetrol.i18n import _


class CalculatorError(Exception):
    pass


_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: np.power,
    ast.BitAnd: np.logical_and,
    ast.BitOr: np.logical_or,
}
_UNARY = {ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Invert: np.logical_not}
_COMPARE = {
    ast.Lt: np.less,
    ast.LtE: np.less_equal,
    ast.Gt: np.greater,
    ast.GtE: np.greater_equal,
    ast.Eq: np.equal,
    ast.NotEq: np.not_equal,
}
FUNCTIONS = {
    "log10": np.log10,
    "log": np.log,
    "ln": np.log,
    "exp": np.exp,
    "sqrt": np.sqrt,
    "abs": np.abs,
    "clip": np.clip,
    "min": np.fmin,
    "max": np.fmax,
    "where": np.where,
    "isnan": np.isnan,
    "round": np.round,
}
CONSTANTS = {"pi": np.pi, "e": np.e, "nan": np.nan, "NaN": np.nan, "NAN": np.nan}

_MAX_LEN = 2000


def _quote(name: str) -> str:
    return f"curve({name!r})"


def evaluate(expression: str, curves: dict[str, np.ndarray]) -> np.ndarray:
    """Evaluates the expression. Curves whose names are not valid identifiers
    (e.g. `K-3104`) are written as `curve("K-3104")` or in brackets `[K-3104]`."""
    if len(expression) > _MAX_LEN:
        raise CalculatorError(_("expression too long"))
    expr = re.sub(r"\[([^\[\]]+)\]", lambda m: _quote(m.group(1).strip()), expression)
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as e:
        raise CalculatorError(_("syntax error near column {column}").format(column=e.offset)) from e

    size = len(next(iter(curves.values()))) if curves else None
    with np.errstate(all="ignore"):
        result = _eval(tree.body, curves)
    result = np.asarray(result, dtype=float)
    if result.ndim == 0:
        if size is None:
            raise CalculatorError(_("the expression does not use any curve"))
        result = np.full(size, float(result))
    if size is not None and result.shape != (size,):
        raise CalculatorError(_("the result does not have the size of the curves"))
    result[~np.isfinite(result)] = np.nan
    return result


def _eval(node, curves):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise CalculatorError(_("only numbers are allowed"))
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id in curves:
            return np.asarray(curves[node.id], dtype=float)
        if node.id in CONSTANTS:
            return CONSTANTS[node.id]
        raise CalculatorError(_("unknown curve: {name}").format(name=node.id))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](_eval(node.left, curves), _eval(node.right, curves))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval(node.operand, curves))
    if isinstance(node, ast.BoolOp):
        fn = np.logical_and if isinstance(node.op, ast.And) else np.logical_or
        out = _eval(node.values[0], curves)
        for v in node.values[1:]:
            out = fn(out, _eval(v, curves))
        return out
    if isinstance(node, ast.Compare):
        left = _eval(node.left, curves)
        out = None
        for op, comp in zip(node.ops, node.comparators, strict=True):
            if type(op) not in _COMPARE:
                raise CalculatorError(_("comparison not allowed"))
            right = _eval(comp, curves)
            r = _COMPARE[type(op)](left, right)
            out = r if out is None else np.logical_and(out, r)
            left = right
        return out
    if isinstance(node, ast.IfExp):
        return np.where(_eval(node.test, curves), _eval(node.body, curves), _eval(node.orelse, curves))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        name = node.func.id
        if name == "curve":
            if (
                len(node.args) != 1
                or not isinstance(node.args[0], ast.Constant)
                or not isinstance(node.args[0].value, str)
            ):
                raise CalculatorError(_('usage: curve("NAME")'))
            key = node.args[0].value
            if key not in curves:
                raise CalculatorError(_("unknown curve: {name}").format(name=key))
            return np.asarray(curves[key], dtype=float)
        if name in FUNCTIONS:
            args = [_eval(a, curves) for a in node.args]
            try:
                return FUNCTIONS[name](*args)
            except TypeError as e:
                raise CalculatorError(_("invalid arguments for {function}()").format(function=name)) from e
        raise CalculatorError(_("function not allowed: {function}").format(function=name))
    raise CalculatorError(_("element not allowed in the expression: {element}").format(element=type(node).__name__))


def referenced_names(expression: str) -> set[str]:
    expr = re.sub(r"\[([^\[\]]+)\]", lambda m: _quote(m.group(1).strip()), expression)
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return set()
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id not in FUNCTIONS and n.id not in CONSTANTS and n.id != "curve":
            names.add(n.id)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "curve" and n.args:
            a = n.args[0]
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                names.add(a.value)
    return names


def curve_ref(mnemonic: str) -> str:
    """How to write a curve name inside a formula."""
    return (
        mnemonic
        if mnemonic.isidentifier() and mnemonic not in FUNCTIONS and mnemonic not in CONSTANTS
        else f"[{mnemonic}]"
    )
