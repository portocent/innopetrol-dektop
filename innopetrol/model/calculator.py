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
from collections.abc import Callable

import numpy as np

from innopetrol.i18n import _


class CalculatorError(Exception):
    pass


_BINOPS: dict[type, Callable] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: np.power,
    ast.BitAnd: np.logical_and,
    ast.BitOr: np.logical_or,
}
_UNARY: dict[type, Callable] = {ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Invert: np.logical_not}
_COMPARE: dict[type, Callable] = {
    ast.Lt: np.less,
    ast.LtE: np.less_equal,
    ast.Gt: np.greater,
    ast.GtE: np.greater_equal,
    ast.Eq: np.equal,
    ast.NotEq: np.not_equal,
}
FUNCTIONS: dict[str, Callable] = {
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


Curves = dict[str, np.ndarray]


def _eval(node: ast.AST, curves: Curves):
    """Evaluates one node of the expression tree; every allowed node type has its own handler."""
    handler = _HANDLERS.get(type(node))
    if handler is None:
        raise _not_allowed(node)
    return handler(node, curves)


def _not_allowed(node: ast.AST) -> CalculatorError:
    return CalculatorError(_("element not allowed in the expression: {element}").format(element=type(node).__name__))


def _curve(name: str, curves: Curves) -> np.ndarray:
    if name not in curves:
        raise CalculatorError(_("unknown curve: {name}").format(name=name))
    return np.asarray(curves[name], dtype=float)


def _eval_constant(node: ast.Constant, curves: Curves):
    if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
        raise CalculatorError(_("only numbers are allowed"))
    return float(node.value)


def _eval_name(node: ast.Name, curves: Curves):
    if node.id not in curves and node.id in CONSTANTS:
        return CONSTANTS[node.id]
    return _curve(node.id, curves)


def _eval_binop(node: ast.BinOp, curves: Curves):
    op = _BINOPS.get(type(node.op))
    if op is None:
        raise _not_allowed(node)
    return op(_eval(node.left, curves), _eval(node.right, curves))


def _eval_unaryop(node: ast.UnaryOp, curves: Curves):
    op = _UNARY.get(type(node.op))
    if op is None:
        raise _not_allowed(node)
    return op(_eval(node.operand, curves))


def _eval_boolop(node: ast.BoolOp, curves: Curves):
    fn = np.logical_and if isinstance(node.op, ast.And) else np.logical_or
    out = _eval(node.values[0], curves)
    for v in node.values[1:]:
        out = fn(out, _eval(v, curves))
    return out


def _eval_compare(node: ast.Compare, curves: Curves):
    """Chained comparisons (0 < PHIE < 0.3) are combined with a logical and, as in Python."""
    left = _eval(node.left, curves)
    out = None
    for op, comp in zip(node.ops, node.comparators, strict=True):
        if type(op) not in _COMPARE:
            raise CalculatorError(_("comparison not allowed"))
        right = _eval(comp, curves)
        result = _COMPARE[type(op)](left, right)
        out = result if out is None else np.logical_and(out, result)
        left = right
    return out


def _eval_ifexp(node: ast.IfExp, curves: Curves):
    return np.where(_eval(node.test, curves), _eval(node.body, curves), _eval(node.orelse, curves))


def _eval_call(node: ast.Call, curves: Curves):
    if not isinstance(node.func, ast.Name) or node.keywords:
        raise _not_allowed(node)
    name = node.func.id
    if name == "curve":
        arg = node.args[0] if len(node.args) == 1 else None
        if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
            raise CalculatorError(_('usage: curve("NAME")'))
        return _curve(arg.value, curves)
    if name not in FUNCTIONS:
        raise CalculatorError(_("function not allowed: {function}").format(function=name))
    args = [_eval(a, curves) for a in node.args]
    try:
        return FUNCTIONS[name](*args)
    except TypeError as e:
        raise CalculatorError(_("invalid arguments for {function}()").format(function=name)) from e


_HANDLERS: dict[type, Callable] = {
    ast.Constant: _eval_constant,
    ast.Name: _eval_name,
    ast.BinOp: _eval_binop,
    ast.UnaryOp: _eval_unaryop,
    ast.BoolOp: _eval_boolop,
    ast.Compare: _eval_compare,
    ast.IfExp: _eval_ifexp,
    ast.Call: _eval_call,
}


def curve_ref(mnemonic: str) -> str:
    """How to write a curve name inside a formula."""
    return (
        mnemonic
        if mnemonic.isidentifier() and mnemonic not in FUNCTIONS and mnemonic not in CONSTANTS
        else f"[{mnemonic}]"
    )
