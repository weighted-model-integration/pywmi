from pysmt.exceptions import PysmtTypeError
from pysmt.shortcuts import Symbol, Pow, Int, Real
from pysmt.typing import REAL

from pywmi.smt_math import get_inequality_dict, get_inequality_smt, Polynomial


def test_conversion():
    x, y, z = [Symbol(n, REAL) for n in "xyz"]
    formula = x * 2 + 3 * y - z + 9 < (5 * z + 2.5) * 2
    # 2x + 3y - z + 9 < 10z + 5
    # 2/4x + 3/4y - 11/4z + 1 <= 0
    should_be = {("x",): 2/4, ("y",): 3/4, ("z",): -11/4, (): 1}
    assert get_inequality_dict(formula) == should_be
    get_inequality_smt(formula)

    formula = 2*x <= 0
    should_be = {("x",): 1, (): 0}
    assert get_inequality_dict(formula) == should_be
    get_inequality_smt(formula)

    formula = 2*x <= 0.0001
    should_be = {("x",): 2 * 1 / 0.0001, (): -1}
    assert get_inequality_dict(formula) == should_be
    get_inequality_smt(formula)


def test_conversion_negative_factor():
    x, y, z = [Symbol(n, REAL) for n in "xyz"]
    formula = (-x <= 0)
    should_be = {("x",): -1, (): 0}
    assert get_inequality_dict(formula) == should_be


def test_conversion_non_linear_error():
    x, y, z = [Symbol(n, REAL) for n in "xyz"]
    formula = ((-x + 2) * y <= 0)
    try:
        get_inequality_dict(formula)
        assert False
    except ValueError:
        assert True


def test_polynomial_from_smt():
    x, y, z = [Symbol(n, REAL) for n in "xyz"]
    formula = (x * 2 + y * y * 3 + 3) * (x * 0.5 + z + 5)
    should_be = {
        ("x", "x"): 1.0, ("x", "z"): 2.0,
        ("x", "y", "y"): 1.5, ("y", "y", "z"): 3.0, ("y", "y"): 15.0,
        ("x",): 11.5, ("z",): 3.0, (): 15.0
    }
    assert Polynomial.from_smt(formula).poly_dict == should_be


def test_polynomial_from_smt_pow():
    x, y, z = [Symbol(n, REAL) for n in "xyz"]
    formula = Pow(x, Real(2)) * 2
    should_be = {("x", "x"): 2.0}
    assert Polynomial.from_smt(formula).poly_dict == should_be


def test_polynomial_from_smt_constant():
    try:
        assert Polynomial.from_smt(Real(1.0)).to_smt() == Real(1.0)
    except Exception:
        assert False

def test_polynomial_hash():
    polynomial = Polynomial({("x", "x"): 2.0})
    hash(polynomial)
