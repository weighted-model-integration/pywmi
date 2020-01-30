import pytest

from .examples import inspect_manual, inspect_density, get_examples
from pywmi.engines.pyxadd.engine import PyXaddEngine

try:
    import psipy
    psipy_installed = True
except ImportError:
    psipy_installed = False


REL_ERROR = 0.000001


@pytest.mark.skipif(not psipy_installed, reason="PSI backend is not installed")
def test_pyxadd_debug():
    import logging
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(level=logging.DEBUG)
    inspect_density(PyXaddEngine(), get_examples()[3])


@pytest.mark.skipif(not psipy_installed, reason="PSI backend is not installed")
def test_manual():
    inspect_manual(PyXaddEngine(), REL_ERROR)


@pytest.mark.skipif(not psipy_installed, reason="PSI backend is not installed")
@pytest.mark.parametrize("e", get_examples())
def test_pa(e):
    inspect_density(PyXaddEngine(), e)
