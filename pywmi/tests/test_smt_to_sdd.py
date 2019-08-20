import pysmt.shortcuts as smt
import pytest

from pywmi import Domain
from pywmi.engines.xsdd.smt_to_sdd import SddConversionWalker, convert_function, recover_formula
from pywmi.smt_print import pretty_print
from pywmi.smt_math import PolynomialAlgebra

try:
    from pysdd.sdd import SddManager
except ImportError:
    SddManager = None

pytestmark = pytest.mark.skipif(SddManager is None, reason="pysdd is not installed")


def test_convert_weight():
    converter = SddConversionWalker(SddManager(), PolynomialAlgebra(), False)
    x, y = smt.Symbol("x", smt.REAL), smt.Symbol("y", smt.REAL)
    a = smt.Symbol("a", smt.BOOL)
    formula = smt.Ite((a & (x > 0) & (x < 10) & (x * 2 <= 20) & (y > 0) & (y < 10)) | (x > 0) & (x < y) & (y < 20), x + y, x * y) + 2
    result = converter.walk_smt(formula)
    print(result)
    print(converter.abstractions)
    print(converter.var_to_lit)


def test_convert_support():
    converter = SddConversionWalker(SddManager(), PolynomialAlgebra(), True)
    x, y = smt.Symbol("x", smt.REAL), smt.Symbol("y", smt.REAL)
    a = smt.Symbol("a", smt.BOOL)
    formula = ((x < 0) | (~a & (x < -1))) | smt.Ite(a, x < 4, x < 8)
    print(pretty_print(formula))
    result = converter.walk_smt(formula)
    print(result)
    print(converter.abstractions)
    print(converter.var_to_lit)
    recovered = recover_formula(result, converter.abstractions, converter.var_to_lit)
    print(pretty_print(recovered))
    with smt.Solver() as solver:
        solver.add_assertion(~smt.Iff(formula, recovered))
        print(pretty_print(formula))
        print(pretty_print(recovered))
        if solver.solve():
            print(solver.get_model())
            assert False


def test_convert_weight2():
    domain = Domain.make(["a", "b"], ["x", "y"], [(0, 1), (0, 1)])
    a, b, x, y = domain.get_symbols(domain.variables)
    ite_a = smt.Ite(a, smt.Real(0.6), smt.Real(0.4))
    ite_b = smt.Ite(b, smt.Real(0.8), smt.Real(0.2))
    ite_x = smt.Ite(x >= smt.Real(0.5), smt.Real(0.5) * x + smt.Real(0.1) * y, smt.Real(0.1) * x + smt.Real(0.7) * y)
    weight = ite_a * ite_b * ite_x

    algebra = PolynomialAlgebra()
    abstractions_c, var_to_lit_c = dict(), dict()
    converted_c = convert_function(smt.Real(0.6), SddManager(), algebra, abstractions_c, var_to_lit_c)
    for p, s in converted_c.sdd_dict.items():
        print("{}: {}".format(p, recover_formula(s, abstractions_c, var_to_lit_c)))
    assert len(converted_c.sdd_dict) == 1

    abstractions_a, var_to_lit_a = dict(), dict()
    converted_a = convert_function(ite_a, SddManager(), algebra, abstractions_a, var_to_lit_a)
    for p, s in converted_a.sdd_dict.items():
        print("{}: {}".format(p, recover_formula(s, abstractions_a, var_to_lit_a)))
    assert len(converted_a.sdd_dict) == 2

    converted_b = convert_function(ite_b, SddManager(), algebra)
    assert len(converted_b.sdd_dict) == 2

    print("X")
    abstractions_x, var_to_lit_x = dict(), dict()
    converted_x = convert_function(ite_x, SddManager(), algebra, abstractions_x, var_to_lit_x)
    for p, s in converted_x.sdd_dict.items():
        print("{}: {}".format(p, recover_formula(s, abstractions_x, var_to_lit_x)))
    assert len(converted_x.sdd_dict) == 2

    converted = convert_function(weight, SddManager(), algebra)
    assert len(converted.sdd_dict) == 2 * 2 * 2
