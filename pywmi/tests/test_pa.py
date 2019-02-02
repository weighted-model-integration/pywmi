import pytest

from examples import get_examples, inspect_density, inspect_manual, inspect_infinite_without_domain_bounds
from pywmi import PredicateAbstractionEngine
from pywmi.engines.pa import WMI

REL_ERROR = 0.000001


def pa_factory(d, s, w):
    return PredicateAbstractionEngine(d, s, w)


@pytest.mark.skipif(WMI is None, reason="PA solver is not installed")
def test_manual():
    inspect_manual(pa_factory, REL_ERROR)


@pytest.mark.skipif(WMI is None, reason="PA solver is not installed")
def test_pa():
    for e in get_examples():
        inspect_density(pa_factory, e)


@pytest.mark.skipif(WMI is None, reason="PA solver is not installed")
def test_infinity():
    pytest.skip("Infinite bounds are not yet correctly supported")
    inspect_infinite_without_domain_bounds(pa_factory, True)
