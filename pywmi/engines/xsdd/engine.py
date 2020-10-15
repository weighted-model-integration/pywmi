from collections import defaultdict
from typing import Dict, List, Tuple, Set, Union, Any, Optional, Iterable
import logging
from itertools import chain

from pysmt.typing import REAL
from pysmt.environment import get_env
import pysmt.shortcuts as smt

from pywmi import Domain
from pywmi.smt_math import (
    Polynomial,
    LinearInequality,
    BoundsWalker,
    PolynomialAlgebra,
    implies,
)
from pywmi.engine import Engine
from pywmi.engines.pyxadd.algebra import PyXaddAlgebra
from pywmi.engines.pyxadd.decision import Decision

from pywmi.engines.algebraic_backend import (
    AlgebraBackend,
    IntegrationBackend,
    PsiPiecewisePolynomialAlgebra,
)
from pywmi.engines.convex_integrator import ConvexIntegrationBackend
from pywmi.engines.xsdd.vtrees.vtree import balanced, bami

from .semiring import amc, Semiring, SddWalker, walk
from .literals import extract_and_replace_literals, LiteralInfo
from .piecewise import split_up_function
from .smt_to_sdd import compile_to_sdd
from .draw import sdd_to_dot_file
from pywmi.engines.xsdd.vtrees.vtree import Vtree


IntegratorAndAlgebra = Union[AlgebraBackend, IntegrationBackend]
logger = logging.getLogger(__name__)


class ConvexWMISemiring(Semiring):
    def __init__(self, literals: LiteralInfo):
        self.literals = literals

    def times_neutral(self):
        return [(smt.TRUE(), set())]

    def plus_neutral(self):
        return []

    def times(self, a, b, index=None):
        result = []
        for f1, v1 in a:
            for f2, v2 in b:
                result.append((f1 & f2, v1 | v2))
        return result

    def plus(self, a, b, index=None):
        return a + b

    def negate(self, a):
        raise NotImplementedError()

    def weight(self, a):
        var = self.literals.inv_numbered[abs(a)]
        abstraction = self.literals[var]
        if isinstance(abstraction, str):
            return [(smt.TRUE(), {abstraction})]
        else:
            if a < 0:
                abstraction = ~abstraction
            return [(abstraction, set())]

    def positive_weight(self, a):
        raise NotImplementedError()


class NonConvexWMISemiring(Semiring):
    def __init__(self, algebra, literals: LiteralInfo):
        self.algebra = algebra
        self.literals = literals

    def times_neutral(self):
        return self.algebra.one(), set()

    def plus_neutral(self):
        return self.algebra.zero(), set()

    def times(self, a, b, index=None):
        return self.algebra.times(a[0], b[0]), a[1] | b[1]

    def plus(self, a, b, index=None):
        return self.algebra.plus(a[0], b[0]), a[1] | b[1]

    def negate(self, a):
        raise NotImplementedError()

    def weight(self, a):
        var = self.literals.inv_numbered[abs(a)]
        abstraction = self.literals[var]
        if isinstance(abstraction, str):
            return self.algebra.one(), {abstraction}
        else:
            if a < 0:
                abstraction = ~abstraction
            return (
                LinearInequality.from_smt(abstraction).to_expression(self.algebra),
                set(),
            )

    def positive_weight(self, a):
        raise NotImplementedError()


class BaseXsddEngine(Engine):
    def __init__(
        self,
        domain,
        support,
        weight,
        exact,
        *,
        algebra: Optional[IntegratorAndAlgebra] = None,
        find_conflicts=False,
        ordered=False,
        vtree_strategy=bami,
        minimize=False,
    ):

        super().__init__(domain, support, weight, exact)
        try:
            from pysdd.sdd import SddManager, SddNode
        except ImportError as e:
            from pywmi.errors import InstallError

            raise InstallError(
                f"{type(self).__name__} requires the pysdd package"
            ) from e

        self.algebra = (
            algebra or PsiPiecewisePolynomialAlgebra()
        )  # Algebra used to solve SMT theory
        self.find_conflicts = find_conflicts
        self.ordered = ordered
        self.vtree_strategy = vtree_strategy
        self.minimize = minimize  # Use SDD minimization as implemented in PySDD

    def get_samples(self, n):
        raise NotImplementedError()

    def collect_conflicts(self):
        conflicts = []
        inequalities = list(
            BoundsWalker(True).walk_smt(self.support)
            | BoundsWalker(True).walk_smt(self.weight)
        )
        for i in range(len(inequalities) - 1):
            for j in range(i + 1, len(inequalities)):
                if (
                    inequalities[i].get_free_variables()
                    == inequalities[j].get_free_variables()
                ):
                    if implies(inequalities[i], inequalities[j]):
                        conflicts.append(smt.Implies(inequalities[i], inequalities[j]))
                        logger.debug("%s => %s", inequalities[i], inequalities[j])
                    if implies(~inequalities[i], inequalities[j]):
                        conflicts.append(smt.Implies(~inequalities[i], inequalities[j]))
                        logger.debug("%s => %s", ~inequalities[i], inequalities[j])
                    if implies(inequalities[j], inequalities[i]):
                        conflicts.append(smt.Implies(inequalities[j], inequalities[i]))
                        logger.debug("%s => %s", inequalities[j], inequalities[i])
                    if implies(~inequalities[j], inequalities[i]):
                        conflicts.append(smt.Implies(~inequalities[j], inequalities[i]))
                        logger.debug("%s => %s", ~inequalities[j], inequalities[i])
        return conflicts

    def get_labels_and_weight(self):
        return dict(), self.weight

    def compute_volume(self, add_bounds=True):
        if add_bounds:
            return self.with_constraint(self.domain.get_bounds()).compute_volume(False)

        # The algebra used for describing the given SMT theory (which hopefully complies)
        # Not to be confused with self.algebra, which is used to actually
        # integrate and solve the SMT theory
        descr_algebra = self.get_weight_algebra()

        # Calculate base support
        base_support = self.support
        if self.find_conflicts:
            base_support = smt.And(*self.collect_conflicts()) & base_support

        labeling_dict, weight_function = self.get_labels_and_weight()
        # piecewise_function contains a dict of weight -> support pairs
        piecewise_function = split_up_function(
            weight_function, descr_algebra, get_env()
        )

        if isinstance(self.algebra, PyXaddAlgebra):
            _, _, all_support_literals = extract_and_replace_literals(base_support)
            vtree = self.get_vtree(base_support, all_support_literals)
            all_literals = [n.var for n in vtree.all_leaves()]

            for lit in all_literals:
                test = all_support_literals[lit]
                if not isinstance(test, str):
                    self.algebra.pool.bool_test(Decision(test))

        volume = self.compute_volume_from_pieces(
            base_support, piecewise_function, labeling_dict
        )
        return self.algebra.to_float(volume)

    def get_weight_algebra(self):
        raise NotImplementedError

    def get_vtree(self, support, literals: LiteralInfo):
        return self.vtree_strategy(literals)

    def get_sdd(self, logic_support, literals: LiteralInfo, vtree: Vtree):
        return compile_to_sdd(logic_support, literals, vtree)

    def compute_volume_from_pieces(
        self, base_support, piecewise_function, labeling_dict
    ):
        raise NotImplementedError()

    def copy(self, domain, support, weight, exact, **kwargs):
        return type(self)(
            domain,
            support,
            weight,
            algebra=self.algebra,
            find_conflicts=self.find_conflicts,
            ordered=self.ordered,
            vtree_strategy=self.vtree_strategy,
            minimize=self.minimize,
            **kwargs,
        )

    def __str__(self):
        solver_string = ""
        if self.find_conflicts:
            solver_string += ":prune"
        if self.ordered:
            solver_string += ":order"
        if self.vtree_strategy:
            solver_string += ":VS={}".format(self.vtree_strategy.__name__)
        if self.minimize:
            solver_string += ":minimize"
        return solver_string

    def __repr__(self):
        return str(self)


class XsddEngine(BaseXsddEngine):
    "Implementation without factorizing"

    def __init__(
        self,
        domain,
        support,
        weight,
        *,
        algebra: Optional[IntegratorAndAlgebra] = None,
        convex_backend: ConvexIntegrationBackend = None,
        **kwargs,
    ):

        algebra = algebra or PsiPiecewisePolynomialAlgebra()
        super().__init__(
            domain,
            support,
            weight,
            convex_backend.exact if convex_backend else algebra.exact,
            algebra=algebra,
            **kwargs,
        )
        self.backend = convex_backend

    def copy(self, domain, support, weight, **kwargs):
        return super().copy(
            domain,
            support,
            weight,
            self.backend.exact,
            convex_backend=self.backend,
            **kwargs,
        )

    def get_weight_algebra(self):
        return PolynomialAlgebra()

    def compute_volume_from_pieces(
        self, base_support, piecewise_function, labeling_dict
    ):
        volume = self.algebra.zero()
        for i, (w_weight, w_support) in enumerate(piecewise_function.pieces.items()):
            support = w_support & base_support
            if not self.backend:
                _, logic_support, literals = extract_and_replace_literals(support)
                vtree = self.get_vtree(support, literals)
                support_sdd = self.get_sdd(logic_support, literals, vtree)
                if logger.getEffectiveLevel() == logging.DEBUG:
                    filename = f"sdd_{i}.dot"
                    sdd_to_dot_file(support_sdd, literals, filename)
                    logger.debug(f"saved SDD to {filename}")

                semiring_algebra = self.algebra
                semiring = NonConvexWMISemiring(semiring_algebra, literals)
                expression, variables = amc(semiring, support_sdd)
                expression = semiring_algebra.times(
                    expression, w_weight.to_expression(semiring_algebra)
                )
                vol = semiring_algebra.integrate(
                    self.domain, expression, self.domain.real_vars
                )
                missing_variable_count = len(self.domain.bool_vars) - len(variables)
                bool_worlds = semiring_algebra.power(
                    semiring_algebra.real(2), missing_variable_count
                )
                vol = semiring_algebra.times(vol, bool_worlds)
                volume = semiring_algebra.plus(volume, vol)

            else:
                _, logic_support, literals = extract_and_replace_literals(support)
                sdd_logic_support = compile_to_sdd(
                    formula=logic_support, literals=literals, vtree=None
                )
                convex_supports = amc(ConvexWMISemiring(literals), sdd_logic_support)
                logger.debug("#convex regions %s", len(convex_supports))
                for convex_support, variables in convex_supports:
                    missing_variable_count = len(self.domain.bool_vars) - len(variables)
                    vol = (
                        self.integrate_convex(convex_support, w_weight.to_smt())
                        * 2 ** missing_variable_count
                    )
                    volume = self.algebra.plus(volume, self.algebra.real(vol))
        return volume

    def integrate_convex(self, convex_support, polynomial_weight):
        try:
            domain = Domain(
                self.domain.real_vars,
                {v: REAL for v in self.domain.real_vars},
                self.domain.var_domains,
            )
            return self.backend.integrate(
                domain,
                BoundsWalker.get_inequalities(convex_support),
                Polynomial.from_smt(polynomial_weight),
            )
        except ZeroDivisionError:
            return 0

    def __str__(self):
        return f"XSDD:BE={self.backend}" + super().__str__()
