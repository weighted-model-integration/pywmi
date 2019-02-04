import pytest
from pysmt.shortcuts import Ite, Real, FALSE, TRUE

from pywmi.engines.rejection import SamplingError
from examples import inspect_manual, inspect_density, inspect_infinite_without_domain_bounds, get_examples
from pywmi import Domain, RejectionEngine, evaluate

SAMPLE_COUNT = 1000000
REL_ERROR = 0.01


def rejection_factory(d, s, w):
    return RejectionEngine(d, s, w, SAMPLE_COUNT)


def test_manual():
    inspect_manual(rejection_factory, REL_ERROR)


def test_infinite():
    inspect_infinite_without_domain_bounds(rejection_factory, False)


def test_examples():
    for density in get_examples():
        inspect_density(rejection_factory, density)


def test_sampling():
    domain = Domain.make(["a", "b"], ["x", "y"], real_bounds=(0, 1))
    a, b, x, y = domain.get_symbols()
    support = (a | b) & (~a | ~b) & (x <= y)
    weight = Ite(a, Real(1), Real(2))
    engine = RejectionEngine(domain, support, weight, 100000)
    required_sample_count = 10000

    samples_weighted, pos_ratio = engine.get_samples(required_sample_count, weighted=True)
    assert samples_weighted.shape[0] == required_sample_count
    assert sum(evaluate(domain, support, samples_weighted)) == len(samples_weighted)
    samples_a = sum(evaluate(domain, a, samples_weighted))
    samples_b = sum(evaluate(domain, b, samples_weighted))
    assert samples_a == pytest.approx(samples_b / 2, rel=0.2)
    assert pos_ratio == pytest.approx(0.25, rel=0.1)

    samples_unweighted, pos_ratio = engine.get_samples(required_sample_count, weighted=False)
    assert samples_unweighted.shape[0] == required_sample_count
    assert sum(evaluate(domain, support, samples_unweighted)) == len(samples_weighted)
    samples_a = sum(evaluate(domain, a, samples_unweighted))
    samples_b = sum(evaluate(domain, b, samples_unweighted))
    assert samples_a == pytest.approx(samples_b, rel=0.1)
    assert pos_ratio == pytest.approx(0.25, rel=0.1)


def test_sampling_max_samples():
    domain = Domain.make([], ["x", "y"], real_bounds=(0, 1))
    x, y = domain.get_symbols()
    support = FALSE()
    weight = Real(1)
    engine = RejectionEngine(domain, support, weight, 10000)
    try:
        engine.get_samples(10, max_samples=100000)
        assert False
    except SamplingError:
        assert True


def test_sampling_stacking():
    domain = Domain.make([], ["x", "y"], real_bounds=(0, 1))
    x, y = domain.get_symbols()
    support = (x <= y)
    weight = Real(1)
    engine = RejectionEngine(domain, support, weight, 10000)
    try:
        engine.get_samples(20, sample_count=10, max_samples=10000)
        assert True
    except ValueError:
        assert False
