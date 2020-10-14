import pytest

from pywmi.errors import InstallError
from .examples import inspect_manual, inspect_density, get_examples
from pywmi.engines.pyxadd.engine import PyXaddEngine

try:
    from ..weight_algebra.psi import psi
except InstallError:
    psi = None


REL_ERROR = 0.000001


@pytest.mark.skipif(psi is None, reason="Psi backend is not installed")
def test_pyxadd_debug():
    import logging

    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(level=logging.DEBUG)
    inspect_density(PyXaddEngine(), get_examples()[3])


@pytest.mark.skipif(psi is None, reason="Psi backend is not installed")
def test_manual():
    inspect_manual(PyXaddEngine(), REL_ERROR)


@pytest.mark.skipif(psi is None, reason="Psi backend is not installed")
@pytest.mark.parametrize("e", get_examples())
def test_pa(e):
    inspect_density(PyXaddEngine(), e)
