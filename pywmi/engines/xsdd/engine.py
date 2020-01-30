from collections import defaultdict
from typing import Dict, List, Tuple, Set, Union, Any, Optional
from typing import Iterable

from pywmi.engines.algebraic_backend import AlgebraBackend, IntegrationBackend
from pywmi.engines.algebraic_backend import PSIAlgebra
from pywmi.engines.convex_integrator import ConvexIntegrationBackend
from pywmi.engines.xsdd.draw import sdd_to_png_file
from pywmi.engines.xsdd.vtree import get_new_manager

try:
    from pysdd.sdd import SddManager, SddNode
except ImportError:
    SddManager, SddNode = None, None

from pysmt.typing import REAL

from pywmi.smt_math import Polynomial, BoundsWalker, LinearInequality, implies
from pywmi.smt_math import PolynomialAlgebra
from .smt_to_sdd import convert_formula, convert_function, extract_labels_and_weight
from pywmi import Domain
from pywmi.engine import Engine
from .semiring import amc, Semiring, SddWalker, walk
from pywmi.engines.pyxadd.algebra import PyXaddAlgebra
from pywmi.engines.pyxadd.decision import Decision

import pysmt.shortcuts as smt
import logging

IntegratorAndAlgebra = Union[AlgebraBackend, IntegrationBackend]
logger = logging.getLogger(__name__)


class ConvexWMISemiring(Semiring):
    def __init__(self, abstractions: Dict, var_to_lit: Dict):
        self.reverse_abstractions = {v: k for k, v in abstractions.items()}
        self.lit_to_var = {v: k for k, v in var_to_lit.items()}

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
        if abs(a) in self.lit_to_var:
            return [(smt.TRUE(), {self.lit_to_var[abs(a)]})]
        else:
            f = self.reverse_abstractions[abs(a)]
            if a < 0:
                f = ~f
            return [(f, set())]

    def positive_weight(self, a):
        raise NotImplementedError()


class NonConvexWMISemiring(Semiring):
    def __init__(self, algebra, abstractions: Dict, var_to_lit: Dict):
        self.algebra = algebra
        self.reverse_abstractions = {v: k for k, v in abstractions.items()}
        self.lit_to_var = {v: k for k, v in var_to_lit.items()}

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
        if abs(a) in self.lit_to_var:
            return self.algebra.one(), {self.lit_to_var[abs(a)]}
        else:
            f = self.reverse_abstractions[abs(a)]
            if a < 0:
                f = ~f
            return LinearInequality.from_smt(f).to_expression(self.algebra), set()

    def positive_weight(self, a):
        raise NotImplementedError()





class BooleanFinder(Semiring):
    def __init__(self, abstractions: Dict, var_to_lit: Dict):
        self.reverse_abstractions = {v: k for k, v in abstractions.items()}
        self.lit_to_var = {v: k for k, v in var_to_lit.items()}

    def times_neutral(self):
        return set()

    def plus_neutral(self):
        return set()

    def times(self, a, b, index=None):
        return a | b

    def plus(self, a, b, index=None):
        return a | b

    def negate(self, a):
        raise NotImplementedError()

    def weight(self, a):
        if abs(a) in self.lit_to_var:
            return {self.lit_to_var[abs(a)]}
        else:
            return set()

    def positive_weight(self, a):
        raise NotImplementedError()


class VariableTagAnalysis(SddWalker):
    def __init__(self, literal_to_groups):
        self.literal_to_groups = literal_to_groups
        self.node_to_groups = dict()

    def walk_true(self, node):
        groups = set()
        self.node_to_groups[node.id] = groups
        return True, groups

    def walk_false(self, node):
        groups = set()
        self.node_to_groups[node.id] = groups
        return False, groups

    def walk_and(self, prime_result, sub_result, prime_node, sub_node):
        prime_feasible, prime_groups = prime_result
        sub_feasible, sub_groups = sub_result
        feasible = prime_feasible and sub_feasible
        groups = (prime_groups | sub_groups) if feasible else set()
        self.node_to_groups[(prime_node.id, sub_node.id)] = groups
        return feasible, groups

    def walk_or(self, child_results, node):
        feasible = any(t[0] for t in child_results)
        groups = set()
        if feasible:
            for _, child_groups in child_results:
                groups |= child_groups
        self.node_to_groups[node.id] = groups
        return feasible, groups

    def walk_literal(self, l, node):
        groups = set(self.literal_to_groups.get(l, []))
        self.node_to_groups[node.id] = groups
        return True, groups




class XsddEngine(Engine):
    def __init__(
            self,
            domain,
            support,
            weight,
            convex_backend: Optional[ConvexIntegrationBackend] = None,
            manager=None,
            algebra: Optional[IntegratorAndAlgebra] = None,
            find_conflicts=False,
            ordered=False,
            balance: Optional[str] = None,
            minimize=False):
        algebra = algebra or PSIAlgebra()
        super().__init__(domain, support, weight, convex_backend.exact if convex_backend else algebra.exact)
        if SddManager is None:
            from pywmi.errors import InstallError
            raise InstallError("NativeXsddEngine requires the pysdd package")
        self.manager = manager or SddManager()
        self.algebra = algebra
        self.backend = convex_backend
        self.find_conflicts = find_conflicts
        self.ordered = ordered
        self.balance = balance
        self.minimize = minimize

    def get_samples(self, n):
        raise NotImplementedError()

    def integrate_convex(self, convex_support, polynomial_weight):
        try:
            domain = Domain(self.domain.real_vars, {v: REAL for v in self.domain.real_vars}, self.domain.var_domains)
            return self.backend.integrate(domain, BoundsWalker.get_inequalities(convex_support),
                                          Polynomial.from_smt(polynomial_weight))
        except ZeroDivisionError:
            return 0

    def get_variable_groups_poly(self, weight: Polynomial, real_vars: List[str]) -> List[Tuple[Set[str], Polynomial]]:
        if len(real_vars) > 0:
            result = []
            found_vars = weight.variables
            for v in real_vars:
                if v not in found_vars:
                    result.append(({v}, Polynomial.from_constant(1)))
            return result + self.get_variable_groups_poly(weight, [])

        if len(weight.poly_dict) > 1:
            return [(weight.variables, weight)]
        elif len(weight.poly_dict) == 0:
            return [(set(), Polynomial.from_constant(0))]
        else:
            result = defaultdict(lambda: Polynomial.from_constant(1))
            for name, value in weight.poly_dict.items():
                if len(name) == 0:
                    result[frozenset()] *= Polynomial.from_constant(value)
                else:
                    for v in name:
                        result[frozenset((v,))] *= Polynomial.from_smt(smt.Symbol(v, smt.REAL))
                    result[frozenset()] *= Polynomial.from_constant(value)
            return list(result.items())

    def collect_conflicts(self):
        conflicts = []
        print(self.support)
        print(self.weight)
        inequalities = list(BoundsWalker(True).walk_smt(self.support) | BoundsWalker(True).walk_smt(self.weight))
        for i in range(len(inequalities) - 1):
            for j in range(i + 1, len(inequalities)):
                if inequalities[i].get_free_variables() == inequalities[j].get_free_variables():
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

    def compute_volume(self, add_bounds=True):
        if add_bounds:
            return self.with_constraint(self.domain.get_bounds()).compute_volume(False)

        abstractions, var_to_lit = dict(), dict()

        poly_algebra = PolynomialAlgebra()
        support = (smt.And(*self.collect_conflicts()) & self.support) if self.find_conflicts else self.support

        labels, weight = None, self.weight

        support_sdd = convert_formula(support, self.manager, poly_algebra, abstractions, var_to_lit)
        piecewise_function = convert_function(weight, self.manager, poly_algebra, abstractions, var_to_lit)

        if self.balance:
            self.manager = get_new_manager(self.domain, abstractions, var_to_lit, self.balance)
            support_sdd = convert_formula(support, self.manager, poly_algebra, abstractions, var_to_lit)
            piecewise_function = convert_function(weight, self.manager, poly_algebra, abstractions, var_to_lit)

        integration_algebra = self.algebra

        volume = integration_algebra.zero()

        for w_weight, world_support in piecewise_function.sdd_dict.items():
            support = support_sdd & world_support
            if not self.backend:
                semiring = NonConvexWMISemiring(integration_algebra, abstractions, var_to_lit)
                expression, variables = amc(semiring, support)
                expression = integration_algebra.times(expression, w_weight.to_expression(integration_algebra))
                volume = integration_algebra.integrate(self.domain, expression, self.domain.real_vars)

                missing_variable_count = len(self.domain.bool_vars) - len(variables)
                bool_worlds = integration_algebra.power(integration_algebra.real(2), missing_variable_count)
                volume = integration_algebra.times(volume, bool_worlds)
            else:
                convex_supports = amc(ConvexWMISemiring(abstractions, var_to_lit), support)
                logger.debug("#convex regions %s", len(convex_supports))
                for convex_support, variables in convex_supports:
                    missing_variable_count = len(self.domain.bool_vars) - len(variables)
                    vol = self.integrate_convex(convex_support, w_weight.to_smt()) * 2 ** missing_variable_count
                    volume = integration_algebra.plus(volume, integration_algebra.real(vol))
        return integration_algebra.to_float(volume)

    def copy(self, domain, support, weight):
        return XsddEngine(
            domain,
            support,
            weight,
            self.backend,
            self.manager,
            self.algebra,
            self.find_conflicts,
            self.ordered,
            self.balance,
            self.minimize
        )

    def __str__(self):
        solver_string = "xsdd:b{}".format(self.backend)
        if self.find_conflicts:
            solver_string += ":prune"
        if self.ordered:
            solver_string += ":order"
        if self.balance:
            solver_string += ":v{}".format(self.balance)
        if self.minimize:
            solver_string += ":minimize"
        return solver_string
