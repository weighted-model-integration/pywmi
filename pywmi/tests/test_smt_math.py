import pytest
from pysmt.exceptions import NoSolverAvailableError
from pysmt.shortcuts import Symbol, Pow, Real, Solver
from pysmt.typing import REAL

from pywmi.errors import InstallError
from pywmi import Domain
from pywmi.engines.latte_backend import LatteIntegrator
from pywmi.engines.xadd import XaddIntegrator
from pywmi.smt_math import get_inequality_dict, get_inequality_smt, Polynomial, LinearInequality, implies


try:
    with Solver() as solver:
        solver_available = True
except NoSolverAvailableError:
    solver_available = False

try:
    LatteIntegrator()
    latte_installed = True
except InstallError:
    latte_installed = False


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


def test_inequality_to_integer():
    x, y = [Symbol(n, REAL) for n in "xy"]
    formula = x * 5/24 + y * 13/17 <= 28/56
    inequality = LinearInequality.from_smt(formula)
    assert inequality.scale_to_integer().to_smt() == (x * 85 + y * 312 <= 204)


@pytest.mark.skipif(not latte_installed, reason="Latte (integrate) is not installed")
def test_latte_backend():
    x, y = [Symbol(n, REAL) for n in "xy"]
    inequalities = [LinearInequality.from_smt(f) for f in [(x >= 0), (x <= y), (y <= 1)]]
    polynomial = Polynomial.from_smt((x*2/3 + 13/15) * (y*1/8 + x))
    domain = Domain.make([], ["x", "y"], [(0, 1), (0, 1)])
    result = LatteIntegrator().integrate(domain, inequalities, polynomial)
    xadd_result = XaddIntegrator().integrate(domain, inequalities, polynomial)
    print(result, xadd_result)
    assert result == pytest.approx(xadd_result, rel=0.001)


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


@pytest.mark.skipif(not solver_available, reason="No SMT solver available")
def test_implies():
    x, y, z = [Symbol(n, REAL) for n in "xyz"]

    term1 = x < 10
    term2 = x < 5
    term3 = y < 5

    assert not implies(term1, term2)
    assert implies(term2, term1)
    assert not implies(term1, term3)
    assert not implies(term2, term3)
    assert not implies(term3, term1)
    assert not implies(term3, term2)
