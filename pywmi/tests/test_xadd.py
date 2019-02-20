from os import path

import pysmt.shortcuts as smt
import pytest
from pysmt.shortcuts import Real, TRUE, read_smtlib, Iff

from pywmi import Domain, XaddEngine, RejectionEngine, smt_to_nested, Density
from pywmi.errors import InstallError
from pywmi.transform import normalize_formula

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

        print(smt_to_nested(clean_weight))

        assert RejectionEngine(domain, ~Iff(support, clean_support), Real(1.0), 1000000).compute_volume() == 0
        assert RejectionEngine(domain, ~Iff(new_support, clean_new_support), Real(1.0), 1000000).compute_volume() == 0

        # plot_formula("new_support", domain, new_support, ["r0", "r1"])
        # plot_formula("clean_new_support", domain, clean_new_support, ["r0", "r1"])

        support = clean_support
        new_support = clean_new_support
        weight = clean_weight

        # print(RejectionEngine(domain, Iff(weight, ~clean_weight), Real(1.0), 1000000).compute_volume())

        # print(smt_to_nested(support))

        print("Problem", i)
        engine = XaddEngine(domain, support, weight, "original")
        print("Volume before starting", engine.compute_volume())
        new_weight = engine.normalize(new_support, paths=False)

        Density(domain, new_support, new_weight).to_file("normalized.json")

        illegal_volume = XaddEngine(domain, ~new_support, new_weight, "mass").compute_volume()
        assert illegal_volume == pytest.approx(0, rel=EXACT_REL_ERROR)

        computed_volume = XaddEngine(domain, TRUE(), new_weight, "mass").compute_volume()
        computed_volume_within = XaddEngine(domain, new_support, new_weight, "mass").compute_volume()
        computed_volume_within2 = XaddEngine(domain, new_support, new_weight).compute_volume()
        computed_volume_within3 = RejectionEngine(domain, new_support, new_weight, 1000000).compute_volume()
        print("pa new_support new_weight", computed_volume_within, "xadd new_support new_weight:", computed_volume_within2, "rej new_support new_weight:", computed_volume_within3)
        assert computed_volume_within == pytest.approx(computed_volume_within2, EXACT_REL_ERROR)
        print("pa true new_weight:", computed_volume, "pa new_support new_weight", computed_volume_within, "pa outside new_support new_weight", illegal_volume)
        assert computed_volume == pytest.approx(1, rel=EXACT_REL_ERROR)
        assert computed_volume_within == pytest.approx(1, rel=EXACT_REL_ERROR)

        illegal_volume = engine.copy_with(support=~new_support, weight=new_weight).compute_volume()
        assert illegal_volume == pytest.approx(0, rel=EXACT_REL_ERROR)


@pytest.mark.skipif(not xadd_installed, reason="XADD engine is not installed")
def test_normalization_negative():
    def get_normalization_file(filename):
        return path.join(path.dirname(__file__), "res", "bug_z_negative", filename)

    domain = Domain.from_file(get_normalization_file("domain"))
    support = domain.get_bounds() & read_smtlib(get_normalization_file("vanilla.support"))
    weight = read_smtlib(get_normalization_file("vanilla.weight"))
    new_support = read_smtlib(get_normalization_file("renorm.support"))
    pa_engine = RejectionEngine(domain, Iff(new_support, ~normalize_formula(new_support)), Real(1), 1000000)
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


@pytest.mark.skipif(not xadd_installed, reason="XADD engine is not installed")
def test_xadd_iff_real():
    domain = Domain.make([], ["x", "y"], real_bounds=(-1, 1))
    x, y = domain.get_symbols()
    c = 0.00000001
    f1 = (x*c > 0) & (x*c <= y*c) & (y*c < c)
    f2 = normalize_formula(f1)

    xadd_vol1 = XaddEngine(domain, (f1 | f2) & (~f1 | ~f2), smt.Real(1.0)).compute_volume()
    xadd_vol2 = XaddEngine(domain, smt.Iff(f1, ~f2), smt.Real(1.0)).compute_volume()
    xadd_vol3 = XaddEngine(domain, ~smt.Iff(f1, f2), smt.Real(1.0)).compute_volume()

    assert xadd_vol1 == pytest.approx(0, EXACT_REL_ERROR)
    assert xadd_vol2 == pytest.approx(0, EXACT_REL_ERROR)
    assert xadd_vol3 == pytest.approx(0, EXACT_REL_ERROR)
