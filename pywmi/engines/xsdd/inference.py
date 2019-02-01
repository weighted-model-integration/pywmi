from typing import Dict

try:
    from pysdd.sdd import SddManager
except ImportError:
    SddManager = None

from pysmt.typing import REAL

from pywmi.engines.integration_backend import IntegrationBackend
from pywmi.smt_math import Polynomial, BoundsWalker
from pywmi.smt_math import PolynomialAlgebra
from .smt_to_sdd import convert_formula, convert_function
from pywmi import Domain
from pywmi.engine import Engine
from .semiring import amc, Semiring

import pysmt.shortcuts as smt


class WMISemiring(Semiring):
    def __init__(self, abstractions: Dict, var_to_lit: Dict):
        self.reverse_abstractions = {v: k for k, v in abstractions.items()}
        self.lit_to_var = {v: k for k, v in var_to_lit.items()}

    def times_neutral(self):
        return [smt.TRUE(), set()]

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


class ContinuousProvenanceSemiring(Semiring):
    def __init__(self, abstractions: Dict, var_to_lit: Dict):
        self.reverse_abstractions = {v: k for k, v in abstractions.items()}
        self.lit_to_var = {v: k for k, v in var_to_lit.items()}
        self.var_dependencies = {}

    def times_neutral(self):
        return dict()

    def plus_neutral(self):
        return dict()

    def plus(self, a, b, index=None):
        assert index
        variables = a | b
        common_variables_children = a & b
        return (variables, common_variables_children)
    def times(self, a, b, index=None):
        assert index
        variables = a | b
        common_variables_children = a & b
        return (variables, common_variables_children)


class IntTagSemiring(Semiring):
    def __init__(self, abstractions: Dict, var_to_lit:Dict, node_var_dependencies: Dict):
        self.reverse_abstractions = {v: k for k, v in abstractions.items()}
        self.lit_to_var = {v: k for k, v in var_to_lit.items()}
        self.int_tags = {}


    def negate(self, a):
        raise NotImplementedError()

    def weight(self, a):
        index = a
        if abs(a) in self.lit_to_var:
            return (set(), set())
        else:
            f = self.reverse_abstractions[abs(a)]
            variables = f.variables()#TODO look up correct method
            return (variables, variables)

    def positive_weight(self, a):
        raise NotImplementedError()


class NativeXsddEngine(Engine):
    def __init__(self, domain, support, weight, backend: IntegrationBackend, manager=None):
        super().__init__(domain, support, weight, backend.exact)
        if SddManager is None:
            from pywmi.errors import InstallError
            raise InstallError("NativeXsddEngine requires the pysdd package")
        self.manager = manager or SddManager()
        self.backend = backend

    def get_samples(self, n):
        raise NotImplementedError()

    def integrate_convex(self, convex_support, polynomial_weight):
        try:
            domain = Domain(self.domain.real_vars, {v: REAL for v in self.domain.real_vars}, self.domain.var_domains)
            return self.backend.integrate(domain, BoundsWalker.get_inequalities(convex_support),
                                          Polynomial.from_smt(polynomial_weight))
        except ZeroDivisionError:
            return 0


    def compute_volume(self, pint=False):
        abstractions, var_to_lit = dict(), dict()

        # conflicts = []
        # inequalities = list(BoundsWalker(True).walk_smt(self.support) | BoundsWalker(True).walk_smt(self.weight))
        # for i in range(len(inequalities) - 1):
        #     for j in range(i + 1, len(inequalities)):
        #         # TODO Find conflicts
        #         if implies(inequalities[i], inequalities[j]):
        #             conflicts.append(smt.Implies(inequalities[i], inequalities[j]))
        #             print(inequalities[i], "=>", inequalities[j])
        #         if implies(inequalities[j], inequalities[i]):
        #             conflicts.append(smt.Implies(inequalities[j], inequalities[i]))
        #             print(inequalities[j], "=>", inequalities[i])

        algebra = PolynomialAlgebra
        support_sdd = convert_formula(self.support, self.manager, algebra, abstractions, var_to_lit)
        piecewise_function = convert_function(self.weight, self.manager, algebra, abstractions, var_to_lit)

        volume = 0
        for world_weight, world_support in piecewise_function.sdd_dict.items():

            support = support_sdd & world_support
            if pint:
                node_var_dependencies, node_var_dependencies_cache = amc(ContinuousProvenanceSemiring(abstractions, var_to_lit), support, return_cache=True)
                int_tags = amc(IntTagSemiring(abstractions, var_to_lit), support)
            else:
                int_tags = {}

            convex_supports = amc(WMISemiring(abstractions, var_to_lit, int_tags), support)
            for convex_support, variables in convex_supports:
                missing_variable_count = len(self.domain.bool_vars) - len(variables)
                vol = self.integrate_convex(convex_support, world_weight.to_smt()) * 2 ** missing_variable_count
                volume += vol
        return volume


    def copy(self, support, weight):
        return NativeXsddEngine(self.domain, support, weight, self.manager)

    def __str__(self):
        return "n-xsdd:b{}".format(self.backend)
