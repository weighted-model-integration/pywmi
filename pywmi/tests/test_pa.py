import pytest

from examples import get_examples, inspect_density, inspect_manual, inspect_infinite_without_domain_bounds
from pywmi import PredicateAbstractionEngine
from pywmi.engines.pa import WMI

REL_ERROR = 0.000001


def make_pa_factory(add_bounds=True):
    def pa_factory(d, s, w):
        return PredicateAbstractionEngine(d, s, w, add_bounds=add_bounds)
    return pa_factory


@pytest.mark.skipif(WMI is None, "PA solver is not installed")
def test_manual():
    inspect_manual(make_pa_factory(), REL_ERROR)


@pytest.mark.skipif(WMI is None, "PA solver is not installed")
def test_pa():
    for e in get_examples():
        inspect_density(make_pa_factory(), e)


@pytest.mark.skipif(WMI is None, "PA solver is not installed")
def test_infinity():
    inspect_infinite_without_domain_bounds(make_pa_factory(), False)
    pytest.skip("Infinite bounds are not yet correctly supported")
    inspect_infinite_without_domain_bounds(make_pa_factory(False), True)
