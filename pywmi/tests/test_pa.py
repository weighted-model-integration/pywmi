import pysmt.shortcuts as smt
import pytest

from .examples import get_examples, inspect_density, inspect_manual, inspect_infinite_without_domain_bounds
from pywmi import PredicateAbstractionEngine, Domain, smt_to_nested
from pywmi.engines.pa import WMI
from pywmi.transform import normalize_formula

REL_ERROR = 0.000001


def pa_factory(d, s, w):
    return PredicateAbstractionEngine(d, s, w)


@pytest.mark.skipif(WMI is None, reason="PA solver is not installed")
def test_manual():
    inspect_manual(pa_factory, REL_ERROR)


@pytest.mark.skipif(True or WMI is None, reason="PA solver is not installed")
@pytest.mark.parametrize("e", get_examples())
def test_pa(e):
    inspect_density(pa_factory, e)


@pytest.mark.skipif(WMI is None, reason="PA solver is not installed")
def test_infinity():
    pytest.skip("Infinite bounds are not yet correctly supported")
    inspect_infinite_without_domain_bounds(pa_factory, True)


@pytest.mark.skipif(WMI is None, reason="PA solver is not installed")
def test_pa_iff_real():
    pytest.skip("Bug fix requires changing PA solver")
    domain = Domain.make([], ["x", "y"], real_bounds=(-1, 1))
    x, y = domain.get_symbols()
    c = 0.00000001
    f1 = (x*c >= 0) & (x*c <= y*c) & (y*c < c)
    f2 = normalize_formula(f1)
    print(smt_to_nested(f2))

    pa_vol1 = PredicateAbstractionEngine(domain, domain.get_bounds() & (f1 | f2) & (~f1 | ~f2), smt.Real(1.0)).compute_volume()
    smt.write_smtlib(domain.get_bounds() & (f1 | f2) & (~f1 | ~f2), "test_pa_iff_real.support")
    smt.write_smtlib(smt.Real(1.0), "test_pa_iff_real.weight")
    pa_vol2 = PredicateAbstractionEngine(domain, smt.Iff(f1, ~f2), smt.Real(1.0)).compute_volume()
    pa_vol3 = PredicateAbstractionEngine(domain, ~smt.Iff(f1, f2), smt.Real(1.0)).compute_volume()

    assert pa_vol1 == pytest.approx(0, REL_ERROR ** 3)
    assert pa_vol2 == pytest.approx(0, REL_ERROR ** 3)
    assert pa_vol3 == pytest.approx(0, REL_ERROR ** 3)
