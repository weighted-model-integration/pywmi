import pysmt.shortcuts as smt
import pytest
from pysmt.exceptions import NoSolverAvailableError
from pywmi.engines.xsdd.literals import extract_and_replace_literals

from pywmi import Domain
from pywmi.engines.xsdd.smt_to_sdd import (
    SddConversionWalker,
    recover_formula,
    compile_to_sdd,
)
from pywmi.smt_print import pretty_print
from pywmi.smt_math import PolynomialAlgebra

try:
    from pysdd.sdd import SddManager
except ImportError:
    SddManager = None

try:
    with smt.Solver() as solver:
        smt_solver_available = True
except NoSolverAvailableError:
    smt_solver_available = False

pytestmark = pytest.mark.skipif(SddManager is None, reason="pysdd is not installed")


@pytest.mark.skip(
    reason="Outdated test, SddConversionWalker only supports logical operations"
)
def test_convert_weight():
    x, y = smt.Symbol("x", smt.REAL), smt.Symbol("y", smt.REAL)
    a = smt.Symbol("a", smt.BOOL)
    weight_function = (
        smt.Ite(
            (a & (x > 0) & (x < 10) & (x * 2 <= 20) & (y > 0) & (y < 10))
            | (x > 0) & (x < y) & (y < 20),
            x + y,
            x * y,
        )
        + 2
    )
    # converter = SddConversionWalker(SddManager(), PolynomialAlgebra(), False)
    # result = converter.walk_smt(weight_function)
    # print(result)
    # print(converter.abstractions)
    # print(converter.var_to_lit)


# @pytest.mark.skipif(not smt_solver_available, reason="No SMT solver available")
# @pytest.mark.skip(reason="Outdated test")
def test_convert_support():
    x, y = smt.Symbol("x", smt.REAL), smt.Symbol("y", smt.REAL)
    a = smt.Symbol("a", smt.BOOL)
    formula = (x < 0) | (~a & (x < -1)) | smt.Ite(a, x < 4, x < 8)
    # Convert formula into abstracted one (replacing inequalities)
    env, repl_formula, literal_info = extract_and_replace_literals(formula)
    result = compile_to_sdd(formula=repl_formula, literals=literal_info, vtree=None)
    recovered = recover_formula(sdd_node=result, literals=literal_info, env=env)
    # print(pretty_print(recovered))
    with smt.Solver() as solver:
        solver.add_assertion(~smt.Iff(formula, recovered))
        # print(pretty_print(formula))
        # print(pretty_print(recovered))
        assert not solver.solve(), f"Expected UNSAT but found model {solver.get_model()}"


@pytest.mark.skip(reason="Function 'convert_function' does not exist anymore")
def test_convert_weight2():
    domain = Domain.make(["a", "b"], ["x", "y"], [(0, 1), (0, 1)])
    a, b, x, y = domain.get_symbols(domain.variables)
    ite_a = smt.Ite(a, smt.Real(0.6), smt.Real(0.4))
    ite_b = smt.Ite(b, smt.Real(0.8), smt.Real(0.2))
    ite_x = smt.Ite(
        x >= smt.Real(0.5),
        smt.Real(0.5) * x + smt.Real(0.1) * y,
        smt.Real(0.1) * x + smt.Real(0.7) * y,
    )
    weight = ite_a * ite_b * ite_x

    algebra = PolynomialAlgebra()
    abstractions_c, var_to_lit_c = dict(), dict()
    converted_c = convert_function(
        smt.Real(0.6), SddManager(), algebra, abstractions_c, var_to_lit_c
    )
    for p, s in converted_c.sdd_dict.items():
        print("{}: {}".format(p, recover_formula(s, abstractions_c, var_to_lit_c)))
    assert len(converted_c.sdd_dict) == 1

    abstractions_a, var_to_lit_a = dict(), dict()
    converted_a = convert_function(
        ite_a, SddManager(), algebra, abstractions_a, var_to_lit_a
    )
    for p, s in converted_a.sdd_dict.items():
        print("{}: {}".format(p, recover_formula(s, abstractions_a, var_to_lit_a)))
    assert len(converted_a.sdd_dict) == 2

    converted_b = convert_function(ite_b, SddManager(), algebra)
    assert len(converted_b.sdd_dict) == 2

    print("X")
    abstractions_x, var_to_lit_x = dict(), dict()
    converted_x = convert_function(
        ite_x, SddManager(), algebra, abstractions_x, var_to_lit_x
    )
    for p, s in converted_x.sdd_dict.items():
        print("{}: {}".format(p, recover_formula(s, abstractions_x, var_to_lit_x)))
    assert len(converted_x.sdd_dict) == 2

    converted = convert_function(weight, SddManager(), algebra)
    assert len(converted.sdd_dict) == 2 * 2 * 2
