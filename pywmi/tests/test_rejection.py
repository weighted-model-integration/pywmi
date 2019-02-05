from examples import inspect_manual, inspect_density, inspect_infinite_without_domain_bounds, get_examples
from pywmi import RejectionEngine

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
