import os
from os import path

import pytest
from pysmt.shortcuts import Real, TRUE, read_smtlib, Iff

from pywmi.errors import InstallError
from pywmi import Domain, XaddEngine, RejectionEngine, PredicateAbstractionEngine, smt_to_nested
from pywmi.smt_print import pretty_print
from pywmi.smt_normalize import normalize_formula
from pywmi.smt_math import implies

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


@pytest.mark.skipif(not xadd_installed, reason="XADD engine is not installed")
def test_normalization():
    def get_normalization_file(filename):
        return path.join(path.dirname(__file__), "res", "renorm_bug", filename)

    for i in range(5):
        domain = Domain.from_file(get_normalization_file("domain.json"))
        support = read_smtlib(get_normalization_file("vanilla.support"))
        weight = read_smtlib(get_normalization_file("vanilla.weight"))
        new_support = read_smtlib(get_normalization_file("renorm_chi_{}.support".format(i)))

        # print(smt_to_nested(support))

        clean_support = normalize_formula(support)
        clean_new_support = normalize_formula(new_support)
        clean_weight = normalize_formula(weight)

        # print(smt_to_nested(support))

        engine = XaddEngine(domain, support, weight)
        new_weight = engine.normalize(new_support, paths=False)

        computed_volume = engine.copy_with(support=new_support, weight=new_weight).compute_volume()
        illegal_volume = engine.copy_with(support=~new_support, weight=new_weight).compute_volume()
        assert computed_volume == pytest.approx(1, rel=EXACT_REL_ERROR)
        assert illegal_volume == pytest.approx(0, rel=EXACT_REL_ERROR)


@pytest.mark.skipif(not xadd_installed, reason="XADD engine is not installed")
def test_normalization_negative():
    def get_normalization_file(filename):
        return path.join(path.dirname(__file__), "res", "bug_z_negative", filename)

    domain = Domain.from_file(get_normalization_file("domain"))
    support = read_smtlib(get_normalization_file("vanilla.support"))
    weight = read_smtlib(get_normalization_file("vanilla.weight"))
    new_support = read_smtlib(get_normalization_file("renorm.support"))
    pa_engine = PredicateAbstractionEngine(domain, Iff(new_support, ~normalize_formula(new_support)), Real(1))
    difference_volume = pa_engine.compute_volume()
    assert difference_volume == pytest.approx(0, EXACT_REL_ERROR ** 2)

    support = normalize_formula(support)
    new_support = normalize_formula(new_support)
    weight = normalize_formula(weight)

    engine = XaddEngine(domain, support, weight)
    new_weight = engine.normalize(new_support, paths=False)

    computed_volume = engine.copy_with(weight=new_weight).compute_volume()
    # print(pa_engine.copy_with(support=domain.get_bounds(), weight=new_weight).compute_volume())
    # print(pa_engine.copy_with(support=new_support, weight=new_weight).compute_volume())
    illegal_volume = engine.copy_with(support=~new_support, weight=new_weight).compute_volume()
    print(computed_volume, illegal_volume)

    # new_new_weight = engine.copy_with(support=domain.get_bounds(), weight=new_weight).normalize(new_support, paths=False)
    # print(pa_engine.copy_with(support=domain.get_bounds(), weight=new_new_weight).compute_volume())

    assert computed_volume == pytest.approx(1, rel=0.1)
    assert illegal_volume == pytest.approx(0, rel=EXACT_REL_ERROR)


