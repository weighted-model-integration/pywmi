import pysmt.shortcuts as smt
import pytest

from pywmi import Domain, sample, evaluate
from pywmi.sample import positive, SamplingError


def test_boolean():
    domain = Domain.make(["a", "b", "c"])
    sample_count = 10
    data = sample.uniform(domain, sample_count)
    assert len(data) == sample_count
    for i in range(sample_count):
        for j in range(3):
            assert data[i, j] == 0 or data[i, j] == 1


def test_real():
    domain = Domain.make([], ["x", "y"], [(-1, 1), (2, 10)])
    sample_count = 10
    data = sample.uniform(domain, sample_count)
    assert len(data) == sample_count
    for i in range(sample_count):
        assert -1 <= data[i, 0] <= 1
        assert 2 <= data[i, 1] <= 10


def test_mixed():
    domain = Domain(
        ["a", "x", "b", "y", "c"],
        {"a": smt.BOOL, "x": smt.REAL, "b": smt.BOOL, "y": smt.REAL, "c": smt.BOOL},
        {"x": (-1, 1), "y": (2, 10)}
    )
    sample_count = 10
    data = sample.uniform(domain, sample_count)
    assert len(data) == sample_count
    for i in range(sample_count):
        assert len(data[i, :]) == len(domain.variables)
        assert data[i, 0] == 0 or data[i, 0] == 1
        assert -1 <= data[i, 1] <= 1
        assert data[i, 2] == 0 or data[i, 2] == 1
        assert 2 <= data[i, 3] <= 10
        assert data[i, 4] == 0 or data[i, 4] == 1


def test_sampling():
    domain = Domain.make(["a", "b"], ["x", "y"], real_bounds=(0, 1))
    a, b, x, y = domain.get_symbols()
    support = (a | b) & (~a | ~b) & (x <= y)
    weight = smt.Ite(a, smt.Real(1), smt.Real(2))

    required_sample_count = 10000
    samples_weighted, pos_ratio = positive(required_sample_count, domain, support, weight)
    assert samples_weighted.shape[0] == required_sample_count
    assert sum(evaluate(domain, support, samples_weighted)) == len(samples_weighted)
    samples_a = sum(evaluate(domain, a, samples_weighted))
    samples_b = sum(evaluate(domain, b, samples_weighted))
    assert samples_a == pytest.approx(samples_b / 2, rel=0.2)
    assert pos_ratio == pytest.approx(0.25, rel=0.1)

    samples_unweighted, pos_ratio = positive(required_sample_count, domain, support)
    assert samples_unweighted.shape[0] == required_sample_count
    assert sum(evaluate(domain, support, samples_unweighted)) == len(samples_weighted)
    samples_a = sum(evaluate(domain, a, samples_unweighted))
    samples_b = sum(evaluate(domain, b, samples_unweighted))
    assert samples_a == pytest.approx(samples_b, rel=0.1)
    assert pos_ratio == pytest.approx(0.25, rel=0.1)


def test_sampling_max_samples():
    domain = Domain.make([], ["x", "y"], real_bounds=(0, 1))
    x, y = domain.get_symbols()
    support = smt.FALSE()
    try:
        positive(10, domain, support, max_samples=100000)
        assert False
    except SamplingError:
        assert True


def test_sampling_stacking():
    domain = Domain.make([], ["x", "y"], real_bounds=(0, 1))
    x, y = domain.get_symbols()
    support = (x <= y)
    try:
        positive(20, domain, support, sample_count=10, max_samples=10000)
        assert True
    except ValueError:
        assert False
