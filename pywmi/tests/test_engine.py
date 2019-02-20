import pytest
from pysmt.exceptions import NoSolverAvailableError
from pysmt.shortcuts import TRUE, Real, Solver, Ite

from pywmi import Domain, PredicateAbstractionEngine
from pywmi.engines.pa import WMI

try:
    with Solver() as solver:
        solver_available = True
except NoSolverAvailableError:
    solver_available = False

STRICT_TOLERANCE = 0.00001


@pytest.mark.skipif((WMI is None) or (not solver_available), reason="PA or SMT solver is not installed")
def test_bounds_added():
    domain = Domain.make([], ["x"], [(0, 1)])
    x, = domain.get_symbols()
    support = (x >= -1) & (x <= 2)
    weight = Real(1.0)
    pa_engine = PredicateAbstractionEngine(domain, support, weight)
    unrestricted = pa_engine.compute_volume(add_bounds=False)
    assert unrestricted == pytest.approx(3, STRICT_TOLERANCE)
    restricted = pa_engine.compute_volume(add_bounds=True)
    assert restricted == pytest.approx(1, STRICT_TOLERANCE)


@pytest.mark.skipif(WMI is None, reason="PA is not installed")
def test_boolean_evidence():
    domain = Domain.make(["a", "b"], ["x", "y"], real_bounds=(0, 1))
    a, b, x, y = domain.get_symbols()
    support = ((a & b) | (~a & ~b)) & (x <= y)
    weight = Ite(a, Real(0.25), Real(0.75)) * Ite(b, Real(0.5), Real(0.5)) * x

    # worlds:
    pa_engine = PredicateAbstractionEngine(domain, support, weight)
    should_be = pa_engine.with_constraint(a).compute_volume()
    computed_volume = pa_engine.with_evidence({a: TRUE()}).compute_volume()

    assert should_be == pytest.approx(computed_volume, rel=STRICT_TOLERANCE)

    should_be = pa_engine.with_constraint(a).compute_probability(x <= y / 2)
    computed_volume = pa_engine.with_evidence({a: TRUE()}).compute_probability(x <= y / 2)
    assert should_be == pytest.approx(computed_volume, rel=STRICT_TOLERANCE)
