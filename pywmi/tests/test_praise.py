import pysmt.shortcuts as smt
import pytest

from pywmi.engines.praise import PraiseEngine, PRAiSEInference
from .examples import get_examples, inspect_density, inspect_manual, inspect_infinite_without_domain_bounds
from pywmi import PredicateAbstractionEngine, Domain, smt_to_nested
from pywmi.transform import normalize_formula

REL_ERROR = 0.000001


def praise_factory(d, s, w):
    return PraiseEngine(d, s, w)


@pytest.mark.skipif(True or PRAiSEInference is None, reason="PA solver is not installed")
def test_praise_manual():
    inspect_manual(praise_factory, REL_ERROR)


@pytest.mark.skipif(True or PRAiSEInference is None, reason="PA solver is not installed")
@pytest.mark.parametrize("e", get_examples())
def test_praise_suite(e):
    inspect_density(praise_factory, e)
