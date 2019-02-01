import pytest as pytest

from examples import get_examples, inspect_density, inspect_manual
from pywmi import PredicateAbstractionEngine

REL_ERROR = 0.000001


@pytest.mark.skip(reason="Unfinished")
def test_pa():
    def pa_engine(domain, support, weight):
        return PredicateAbstractionEngine(domain, support, weight)

    for e in get_examples():
        inspect_density(pa_engine, e)


def test_manual():
    inspect_manual(lambda d, s, w: PredicateAbstractionEngine(d, s, w), REL_ERROR)
