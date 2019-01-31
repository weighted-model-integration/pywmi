import pytest as pytest

from examples import get_examples, inspect_density
from pywmi import PredicateAbstractionEngine


@pytest.mark.skip(reason="Unfinished")
def test_pa():
    def pa_engine(domain, support, weight):
        return PredicateAbstractionEngine(domain, support, weight)

    for e in get_examples():
        inspect_density(pa_engine, e)
