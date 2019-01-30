import pytest
from pysmt.shortcuts import Ite, Real

from pywmi import AdaptiveRejection, RejectionEngine
from pywmi import Domain


SAMPLE_COUNT = 10000
APPROX_ERROR = 0.1
EXACT_ERROR = 0.01


@pytest.mark.skip(reason="Boolean values are currently not supported")
def test_volume():
    domain = Domain.make(["a", "b"], ["x", "y"], [(0, 1), (0, 1)])
    a, b, x, y = domain.get_symbols(domain.variables)
    support = (a | b) & (~a | ~b) & (x >= 0.0) & (x <= y) & (y <= 1.0)
    weight = Ite(a, Real(0.6), Real(0.4)) * Ite(b, Real(0.8), Real(0.2))\
             * (Ite(x >= Real(0.5), Real(0.5) * x + Real(0.1) * y, Real(0.1) * x + Real(0.7) * y))
    engine = AdaptiveRejection(domain, support, weight, SAMPLE_COUNT)
    computed_volume = engine.compute_volume()
    correction_volume_rej = RejectionEngine(domain, support, weight, SAMPLE_COUNT).compute_volume()
    assert computed_volume == pytest.approx(correction_volume_rej, rel=APPROX_ERROR)


@pytest.mark.skip(reason="Boolean values are currently not supported")
def test_adaptive_unweighted():
    domain = Domain.make(["a", "b"], ["x", "y"], [(0, 1), (0, 1)])
    a, b, x, y = domain.get_symbols(domain.variables)
    support = (a | b) & (~a | ~b) & (x >= 0) & (x <= y) & (y <= 1)
    weight = Real(1.0)
    engine = AdaptiveRejection(domain, support, weight, SAMPLE_COUNT, SAMPLE_COUNT / 10)
    computed_volume = engine.compute_volume()
    correction_volume_rej = RejectionEngine(domain, support, weight, SAMPLE_COUNT).compute_volume()
    assert computed_volume == pytest.approx(correction_volume_rej, rel=APPROX_ERROR)


@pytest.mark.skip(reason="Adaptive rejection sampling not fully supported yet")
def test_adaptive_weighted_real():
    domain = Domain.make([], ["x", "y"], [(-5, 10), (-5, 10)])
    x, y = domain.get_symbols(domain.variables)
    support = (x >= -4) & (x <= y) & (y <= 9) & ((y <= -1) | (y >= 6))
    weight = Ite(x <= 2.5, x + y, y * 2)
    engine = AdaptiveRejection(domain, support, weight, SAMPLE_COUNT, SAMPLE_COUNT / 10)
    computed_volume = engine.compute_volume()
    rejection_engine = RejectionEngine(domain, support, weight, SAMPLE_COUNT)
    correction_volume_rej = rejection_engine.compute_volume()
    print(computed_volume, correction_volume_rej, APPROX_ERROR * correction_volume_rej)
    assert computed_volume == pytest.approx(correction_volume_rej, rel=APPROX_ERROR)

    query = x <= y / 2
    prob_adaptive = engine.compute_probability(query)
    prob_rej = rejection_engine.compute_probability(query)
    assert prob_adaptive == pytest.approx(prob_rej, rel=APPROX_ERROR)


@pytest.mark.skip(reason="Adaptive rejection sampling not fully supported yet")
def test_adaptive_unweighted_real():
    domain = Domain.make([], ["x", "y"], [(-5, 10), (-5, 10)])
    x, y = domain.get_symbols(domain.variables)
    support = (x >= -4) & (x <= y) & (y <= 9) & ((y <= -1) | (y >= 6))
    weight = Real(1.0)
    engine = AdaptiveRejection(domain, support, weight, SAMPLE_COUNT, SAMPLE_COUNT / 10)
    computed_volume = engine.compute_volume()
    rejection_engine = RejectionEngine(domain, support, weight, SAMPLE_COUNT)
    correction_volume_rej = rejection_engine.compute_volume()
    print(computed_volume, correction_volume_rej, APPROX_ERROR * correction_volume_rej)
    assert computed_volume == pytest.approx(correction_volume_rej, rel=APPROX_ERROR)

    query = x <= y / 2
    prob_adaptive = engine.compute_probability(query)
    prob_rej = rejection_engine.compute_probability(query)
    assert prob_adaptive == pytest.approx(prob_rej, rel=APPROX_ERROR)
