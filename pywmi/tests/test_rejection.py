import pytest
from pysmt.shortcuts import Ite, Real

from pywmi import Domain, RejectionEngine

SAMPLE_COUNT = 1000000
REL_ERROR = 0.01


def test_manual():
    domain = Domain.make(["a"], ["x"], [(0, 1)])
    a, x, = domain.get_symbols()
    support = (a & (x <= 0.5)) | (x >= 0.2)
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

    engine = RejectionEngine(domain, support, weight, SAMPLE_COUNT)
    assert engine.compute_volume() == pytest.approx(volume, rel=REL_ERROR)

    boolean_query = a
    boolean_result = 0.0315 + 0.006 + 0.1125

    assert engine.compute_probability(boolean_query) == pytest.approx(boolean_result / volume, rel=REL_ERROR)

    real_query = (x <= 0.3)
    # worlds:    a, x <= 0.5, x >= 0.2, x <= 0.3  integrate 0.3 * x, 0.2 <= x <= 0.3 = 0.0075
    #            a, x <= 0.5, x <= 0.2, x <= 0.3  integrate 0.3 * x, 0.0 <= x <= 0.2 = 0.006
    #            a, x >= 0.5, x >= 0.2, x <= 0.3
    #           ~a, x <= 0.5, x >= 0.2, x <= 0.3  integrate 0.7 * x, 0.2 <= x <= 0.3 = 0.0175
    #           ~a, x >= 0.5, x >= 0.2, x <= 0.3
    real_result = 0.0075 + 0.006 + 0.0175

    assert engine.compute_probability(real_query) == pytest.approx(real_result / volume, rel=REL_ERROR)


