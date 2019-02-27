from typing import Union, Callable

import pytest
from pysmt.shortcuts import Ite, Real, TRUE

from pywmi.errors import InstallError, InfiniteVolumeError
from pywmi import Domain, RejectionEngine, XaddEngine, Density
from pywmi.engine import Engine

TEST_SAMPLE_COUNT = 1000000
TEST_RELATIVE_TOLERANCE = 0.05


def sanity_b1_r0():
    domain = Domain.make(["a"])
    a, = domain.get_symbols()
    support = TRUE()
    weight = Ite(a, Real(0.3), Real(0.7))
    queries = [a, ~a]
    return Density(domain, support, weight, queries)


def sanity_b0_r1():
    domain = Domain.make(real_variables=["x"], real_bounds=(0, 1))
    x, = domain.get_symbols()
    support = (x >= 0.25) & (x <= 0.75)
    weight = x + 1
    queries = [x >= 0.5]
    return Density(domain, support, weight, queries)


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
    examples = [
        (sanity_b1_r0, True, False),
        (sanity_b0_r1, False, True),
        (ex1_b2_r2, True, True),
        (ex2_b0_r2, False, True)
    ]
    return [e() for e, b, c in examples if (not exclude_boolean or not b) and (not exclude_continuous or not c)]


def inspect_density(engine_or_factory, density, test_unweighted=True, test_weighted=True, test_volume=True,
                    test_queries=True, test_engine=None):
    if isinstance(engine_or_factory, Engine):
        engine_factory = lambda d, s, w: engine_or_factory.copy(d, s, w)
    else:
        engine_factory = engine_or_factory

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
            computed_volume = engine.copy(density.domain, density.support, trivial_weight).compute_volume()
            actual_volume = test_engine.copy(density.domain, density.support, trivial_weight).compute_volume()
            assert computed_volume == pytest.approx(actual_volume, rel=TEST_RELATIVE_TOLERANCE)
    if test_queries:
        for query in density.queries:
            if test_weighted:
                computed = engine.compute_probability(query)
                actual = test_engine.compute_probability(query)
                assert computed == pytest.approx(actual, rel=TEST_RELATIVE_TOLERANCE)
            if test_unweighted:
                computed = engine.copy(density.domain, density.support, trivial_weight).compute_probability(query)
                actual = test_engine.copy(density.domain, density.support, trivial_weight).compute_probability(query)
                assert computed == pytest.approx(actual, rel=TEST_RELATIVE_TOLERANCE)


def inspect_manual(engine_or_factory: Union[Engine, Callable], rel_error):
    if isinstance(engine_or_factory, Engine):
        engine_factory = lambda d, s, w: engine_or_factory.copy(d, s, w)
    else:
        engine_factory = engine_or_factory

    domain = Domain.make(["a"], ["x"], [(0, 1)])
    a, x, = domain.get_symbols()
    support = ((a & (x <= 0.5)) | (x >= 0.2)) & domain.get_bounds()
    weight = Ite(a, Real(0.3), Real(0.7)) * x
    # worlds:    a, x <= 0.5, x >= 0.2  integrate 0.3 * x, 0.2 <= x <= 0.5 = 0.0315
    #            a, x <= 0.5, x <= 0.2  integrate 0.3 * x, 0.0 <= x <= 0.2 = 0.006
    #            a, x >= 0.5, x <= 0.2
    #            a, x >= 0.5, x >= 0.2  integrate 0.3 * x, 0.5 <= x <= 1.0 = 0.1125
    #           ~a, x <= 0.5, x >= 0.2  integrate 0.7 * x, 0.2 <= x <= 0.5 = 0.0735
    #           ~a, x <= 0.5, x <= 0.2
    #           ~a, x >= 0.5, x <= 0.2
    #           ~a, x >= 0.5, x >= 0.2  integrate 0.7 * x, 0.5 <= x <= 1.0 = 0.2625
    volume = 0.0315 + 0.006 + 0.1125 + 0.0735 + 0.2625

    engine = engine_factory(domain, support, weight)
    computed_volume = engine.compute_volume()
    print(computed_volume, volume)
    assert computed_volume == pytest.approx(volume, rel=rel_error)

    boolean_query = a
    boolean_result = 0.0315 + 0.006 + 0.1125

    assert engine.compute_probability(boolean_query) == pytest.approx(boolean_result / volume, rel=rel_error)

    real_query = (x <= 0.3)
    # worlds:    a, x <= 0.5, x >= 0.2, x <= 0.3  integrate 0.3 * x, 0.2 <= x <= 0.3 = 0.0075
    #            a, x <= 0.5, x <= 0.2, x <= 0.3  integrate 0.3 * x, 0.0 <= x <= 0.2 = 0.006
    #            a, x >= 0.5, x >= 0.2, x <= 0.3
    #           ~a, x <= 0.5, x >= 0.2, x <= 0.3  integrate 0.7 * x, 0.2 <= x <= 0.3 = 0.0175
    #           ~a, x >= 0.5, x >= 0.2, x <= 0.3
    real_result = 0.0075 + 0.006 + 0.0175

    assert engine.compute_probability(real_query) == pytest.approx(real_result / volume, rel=rel_error)


def inspect_infinite_without_domain_bounds(engine_factory, should_be_infinite):
    domain = Domain.make([], ["x"], [(0, 1)])
    x, = domain.get_symbols()
    support = (x >= 0.5)
    weight = Real(1.0)
    engine = engine_factory(domain, support, weight)
    volume = engine.compute_volume(add_bounds=True)
    assert volume == pytest.approx(0.5, rel=TEST_RELATIVE_TOLERANCE)

    try:
        volume = engine.compute_volume(add_bounds=False)
        if should_be_infinite:
            assert (volume is None) or (volume == float("inf"))
        else:
            assert volume == pytest.approx(0.5, rel=TEST_RELATIVE_TOLERANCE)
    except InfiniteVolumeError:
        assert should_be_infinite



