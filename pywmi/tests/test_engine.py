from pysmt.shortcuts import TRUE, Real

from pywmi import RejectionEngine, Domain, PredicateAbstractionEngine
from pywmi.smt_math import implies


def test_bounds_added():
    domain = Domain.make([], ["x"], [(0, 1)])
    x, = domain.get_symbols()
    support = TRUE()
    weight = Real(1.0)
    rej_engine = RejectionEngine(domain, support, weight, 1)
    assert not implies(rej_engine.support, ~((x < 0) | (x > 1)))

    pa_engine = PredicateAbstractionEngine(domain, support, weight)
    assert implies(pa_engine.support, ~(x < 0) & ~(x > 1))

    domain2 = domain.change_bounds({"x": (None, None)})
    pa_engine2 = PredicateAbstractionEngine(domain2, support, weight)
    assert not implies(pa_engine2.support, ~(x < 0) & ~(x > 1))
