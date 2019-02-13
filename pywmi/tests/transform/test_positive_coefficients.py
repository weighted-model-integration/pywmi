import pysmt.shortcuts as smt
from pywmi.transform import make_coefficients_positive
from pywmi.smt_math import Polynomial


def test_constant_positive():
    formula = smt.Real(2)
    result = make_coefficients_positive(formula)
    assert formula == result


def test_constant_negative():
    formula = smt.Real(-2.3)
    result = make_coefficients_positive(formula)
    assert formula == smt.simplify(-result)


def test_constant_boolean():
    formula = smt.Bool(True)
    result = make_coefficients_positive(formula)
    assert formula == result


def test_nested():
    formula = (smt.Symbol("x", smt.REAL) * smt.Real(2) + smt.Real(5.125)) * smt.Real(-1.25)
    positive = (smt.Symbol("x", smt.REAL) * smt.Real(2) + smt.Real(5.125)) * smt.Real(1.25)
    result = make_coefficients_positive(formula)
    assert Polynomial.from_smt(positive) == Polynomial.from_smt(result)



