import pytest
from pysmt.shortcuts import Ite, Real

from pywmi.errors import InstallError
from pywmi import Domain, RejectionEngine, XaddEngine, Density

TEST_SAMPLE_COUNT = 1000000
TEST_RELATIVE_TOLERANCE = 0.05


def ex1_b2_r2():
    domain = Domain.make(["a", "b"], ["x", "y"], [(0, 1), (0, 1)])
    a, b, x, y = domain.get_symbols(domain.variables)
    support = (a | b) & (~a | ~b) & (x >= 0.0) & (x <= y) & (y <= 1.0)
    weight = Ite(a, Real(0.6), Real(0.4)) * Ite(b, Real(0.8), Real(0.2))\
        * (Ite(x >= Real(0.5), Real(0.5) * x + Real(0.1) * y, Real(0.1) * x + Real(0.7) * y))
    return Density(domain, support, weight, [x <= y / 2])


def ex2_b0_r2():
    domain = Domain.make([], ["x", "y"], [(-5, 10), (-5, 10)])
    x, y = domain.get_symbols(domain.variables)
    support = (x >= -4) & (x <= y) & (y <= 9) & ((y <= -1) | (y >= 6))
    weight = Ite(x <= 2.5, x + y, y * 2)
    return Density(domain, support, weight, [x <= y / 2])


def get_examples(exclude_boolean=False, exclude_continuous=False):
    examples = [(ex1_b2_r2, True, True), (ex2_b0_r2, False, True)]
    return [e() for e, b, c in examples if (not exclude_boolean or not b) and (not exclude_continuous or not c)]


def inspect_density(engine_factory, density, test_unweighted=True, test_weighted=True, test_volume=True,
                    test_queries=True, test_engine=None):
    if test_engine is None:
        try:
            test_engine = XaddEngine(density.domain, density.support, density.weight)
        except InstallError:
            test_engine = RejectionEngine(density.domain, density.support, density.weight, TEST_SAMPLE_COUNT)

    engine = engine_factory(density.domain, density.support, density.weight)
    trivial_weight = Real(1.0)
    if test_volume:
        if test_weighted:
            computed_volume = engine.compute_volume()
            actual_volume = test_engine.compute_volume()
            assert computed_volume == pytest.approx(actual_volume, rel=TEST_RELATIVE_TOLERANCE)
        if test_unweighted:
            computed_volume = engine.copy(density.support, trivial_weight).compute_volume()
            actual_volume = test_engine.copy(density.support, trivial_weight).compute_volume()
            assert computed_volume == pytest.approx(actual_volume, rel=TEST_RELATIVE_TOLERANCE)
    if test_queries:
        for query in density.queries:
            if test_weighted:
                computed = engine.compute_probability(query)
                actual = test_engine.compute_probability(query)
                assert computed == pytest.approx(actual, rel=TEST_RELATIVE_TOLERANCE)
            if test_unweighted:
                computed = engine.copy(density.support, trivial_weight).compute_probability(query)
                actual = test_engine.copy(density.support, trivial_weight).compute_probability(query)
                assert computed == pytest.approx(actual, rel=TEST_RELATIVE_TOLERANCE)
