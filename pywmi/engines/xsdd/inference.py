from typing import Dict

from pysdd.sdd import SddManager
from pysmt.typing import REAL

from .smt_to_sdd import recover
from pywmi.smt_print import pretty_print
from .smt_to_sdd import convert
from pywmi import Engine, RejectionEngine, Domain
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


class NativeXsddEngine(Engine):
    def get_samples(self, n):
        raise NotImplementedError()

    def __init__(self, domain, support, weight, manager=None):
        super().__init__(domain, support, weight)
        self.manager = manager or SddManager()

    def integrate_convex(self, convex_support, polynomial_weight):
        try:
            print(pretty_print(smt.simplify(convex_support)))
            print(pretty_print(smt.simplify(polynomial_weight)))
            domain = Domain(self.domain.real_vars, {v: REAL for v in self.domain.real_vars}, self.domain.var_domains)
            result = RejectionEngine(domain, convex_support, polynomial_weight, 100000).compute_volume()
            print(result)
            print()
            return result
        except ZeroDivisionError:
            return 0

    def compute_volume(self):
        abstractions, var_to_lit = dict(), dict()
        support_sdd = convert(self.support, self.manager, abstractions, var_to_lit)
        sdd_dicts = convert(self.weight, self.manager, abstractions, var_to_lit)

        print("Native", sdd_dicts)
        volume = 0
        for world_weight, world_support in sdd_dicts.items():
            print(world_weight)
            convex_supports = amc(WMISemiring(abstractions, var_to_lit), support_sdd & world_support)
            for convex_support, variables in convex_supports:
                missing_variable_count = len(self.domain.bool_vars) - len(variables)
                print(f"Missing variables: {missing_variable_count}")
                volume += self.integrate_convex(convex_support, world_weight.to_smt()) * 2 ** missing_variable_count
        return volume

    def copy(self, support, weight):
        return NativeXsddEngine(self.domain, support, weight, self.manager)