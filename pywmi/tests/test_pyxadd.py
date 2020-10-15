import pytest

from pywmi import RejectionEngine
from pywmi.errors import InstallError
from .examples import inspect_manual, inspect_density, get_examples, TEST_SAMPLE_COUNT
from pywmi.engines.pyxadd.engine import PyXaddEngine

try:
    from ..weight_algebra.psi import psi
except InstallError:
    psi = None


REL_ERROR = 0.000001


def test_pyxadd_debug():
    import logging

    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(level=logging.DEBUG)
    inspect_density(PyXaddEngine(), get_examples()[3])


def test_manual():
    inspect_manual(PyXaddEngine(), REL_ERROR)


@pytest.mark.parametrize("e", get_examples())
def test_pyxadd_automated(e):
    inspect_density(PyXaddEngine(), e, test_engine=RejectionEngine(e.domain, e.support, e.weight, sample_count=TEST_SAMPLE_COUNT))
