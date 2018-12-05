import pysmt.shortcuts as smt

from pywmi import Domain, sample


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
