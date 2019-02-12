import os
from os import path

import pytest
from pysmt.shortcuts import Real, TRUE, read_smtlib

from pywmi.errors import InstallError
from pywmi import Domain, XaddEngine

EXACT_REL_ERROR = 0.00000001

try:
    # noinspection PyTypeChecker
    XaddEngine(None, None, None)
    xadd_installed = True
except InstallError:
    xadd_installed = False


@pytest.mark.skipif(not xadd_installed, reason="XADD engine is not installed")
def test_minus():
    domain = Domain.make([], ["x"], [(0, 1)])
    x, = domain.get_symbols()
    support = TRUE()
    weight = Real(1) - x
    engine = XaddEngine(domain, support, weight)
    assert engine.compute_volume() is not None


def get_normalization_file(filename):
    return path.join(path.dirname(__file__), "res", "renorm_bug", filename)


@pytest.mark.skipif(not xadd_installed, reason="XADD engine is not installed")
def test_normalization():
    for i in range(5):
        domain = Domain.from_file(get_normalization_file("domain.json"))
        support = read_smtlib(get_normalization_file("vanilla.support"))
        weight = read_smtlib(get_normalization_file("vanilla.weight"))
        new_support = read_smtlib(get_normalization_file("renorm_chi_{}.support".format(i)))
        engine = XaddEngine(domain, support, weight)
        new_weight = engine.normalize(new_support, paths=False)

        computed_volume = engine.copy_with(support=new_support, weight=new_weight).compute_volume()
        illegal_volume = engine.copy_with(support=~new_support, weight=new_weight).compute_volume()
        assert computed_volume == pytest.approx(1, rel=EXACT_REL_ERROR)
        assert illegal_volume == pytest.approx(0, rel=EXACT_REL_ERROR)
