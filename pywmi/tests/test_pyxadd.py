import pytest

from .examples import inspect_manual, inspect_density, get_examples
from pywmi.engines.pyxadd.engine import PyXaddEngine


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
def test_pa(e):
    inspect_density(PyXaddEngine(), e)
