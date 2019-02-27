import pysmt.shortcuts as smt
import pytest

from .examples import inspect_manual, inspect_density, inspect_infinite_without_domain_bounds, get_examples
from pywmi import RejectionEngine, Domain, XaddEngine
from pywmi.transform import normalize_formula

SAMPLE_COUNT = 1000000
REL_ERROR = 0.01


def rejection_factory(d, s, w):
    return RejectionEngine(d, s, w, SAMPLE_COUNT)


def test_manual():
    inspect_manual(rejection_factory, REL_ERROR)


def test_infinite():
    inspect_infinite_without_domain_bounds(rejection_factory, False)


@pytest.mark.parametrize("e", get_examples())
def test_examples(e):
    inspect_density(rejection_factory, e)


@pytest.mark.skip("Not ready")
def test_rejection_iff_bool():
    domain = Domain.make(["a", "b"])
    a, b = domain.get_symbols()

    print(domain)
    vol_t = RejectionEngine(domain, smt.TRUE(), smt.Real(1.0), 100000).compute_volume()
    vol1 = RejectionEngine(domain, (a | b) & (~a | ~b), smt.Real(1.0), 100000).compute_volume()
    vol2 = RejectionEngine(domain, smt.Iff(a, ~b), smt.Real(1.0), 100000).compute_volume()
    vol3 = RejectionEngine(domain, ~smt.Iff(a, b), smt.Real(1.0), 100000).compute_volume()

    print(vol1, vol2, vol3, vol_t)

    # print(PredicateAbstractionEngine(domain, a | b, smt.Real(1.0)).compute_volume())
    print(XaddEngine(domain, a | b, smt.Real(1.0)).compute_volume())

    quit()


def test_rejection_iff_real():
    domain = Domain.make([], ["x", "y"], real_bounds=(-1, 1))
    x, y = domain.get_symbols()
    c = 0.00000001
    f1 = (x*c > 0) & (x*c <= y*c) & (y*c < c)
    f2 = normalize_formula(f1)

    rej_vol1 = RejectionEngine(domain, (f1 | f2) & (~f1 | ~f2), smt.Real(1.0), 100000).compute_volume()
    rej_vol2 = RejectionEngine(domain, smt.Iff(f1, ~f2), smt.Real(1.0), 100000).compute_volume()
    rej_vol3 = RejectionEngine(domain, ~smt.Iff(f1, f2), smt.Real(1.0), 100000).compute_volume()

    assert rej_vol1 == pytest.approx(0, REL_ERROR ** 3)
    assert rej_vol2 == pytest.approx(0, REL_ERROR ** 3)
    assert rej_vol3 == pytest.approx(0, REL_ERROR ** 3)
