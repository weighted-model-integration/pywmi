from typing import Dict, Tuple, Set, Union, List, Optional, Any
import logging
import copy
from collections import defaultdict
from functools import reduce
import operator


import pysmt.shortcuts as smt

from pywmi import Domain
from pywmi.smt_math import PolynomialAlgebra, Polynomial, LinearInequality
from pywmi.engines.algebraic_backend import (
    AlgebraBackend,
    IntegrationBackend,
    PSIAlgebra,
)
from pywmi.multimap import multimap
from pywmi.engines.xsdd.smt_to_sdd import extract_labels_and_weight


from .semiring import amc, Semiring, SddWalker, walk
from .engine import BaseXsddEngine, IntegratorAndAlgebra
from .literals import LiteralInfo, extract_and_replace_literals
from .smt_to_sdd import compile_to_sdd
from .draw import sdd_to_dot_file


logger = logging.getLogger(__name__)


class VariableTagAnalysis(SddWalker):
    def __init__(self, literal_to_variables):
        self.literal_to_variables = literal_to_variables
        self.node_to_variable_heights = dict()

    def walk_true(self, node):
        variable_heights = {}
        self.node_to_variable_heights[node.id] = variable_heights
        return True, variable_heights

    def walk_false(self, node):
        variable_heights = {}
        self.node_to_variable_heights[node.id] = variable_heights
        return False, variable_heights

    def walk_and(self, prime_result, sub_result, prime_node, sub_node):
        prime_feasible, prime_variable_heights = prime_result
        sub_feasible, sub_variable_heights = sub_result

        feasible = prime_feasible and sub_feasible

        variable_heights = self._aggregate_heights(
            prime_variable_heights, sub_variable_heights
        )
        variable_heights = {k: v + 1 for k, v in variable_heights.items()}

        self.node_to_variable_heights[(prime_node.id, sub_node.id)] = variable_heights

        return feasible, variable_heights

    def walk_or(self, child_results, node):
        feasible = any(t[0] for t in child_results)
        variable_heights = {}
        if feasible:
            for _, child_variable_heights in child_results:
                variable_heights = self._aggregate_heights(
                    variable_heights, child_variable_heights
                )
        self.node_to_variable_heights[node.id] = variable_heights

        return feasible, variable_heights

    def walk_literal(self, l, node):
        variables = self.literal_to_variables[l]
        variable_heights = {v: 1 for v in variables}
        self.node_to_variable_heights[node.id] = variable_heights
        return True, variable_heights

    def _aggregate_heights(self, a: Dict, b: Dict):
        result = copy.deepcopy(a)
        for k, v in b.items():
            if k in result:
                result[k] = max(result[k], b[k])
            else:
                result[k] = b[k]
        return result


class BooleanFinder(Semiring):
    def __init__(self, literals: LiteralInfo):
        self.inv_boolean_varnums = {
            num: lit
            for num, lit in literals.inv_numbered.items()
            if isinstance(literals[lit], str)
        }

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
        if abs(a) in self.inv_boolean_varnums:
            return {self.inv_boolean_varnums[abs(a)]}
        else:
            return set()

    def positive_weight(self, a):
        raise NotImplementedError()


class FactorizedIntegrator:
    def __init__(
        self,
        domain: Domain,
        literals: LiteralInfo,
        node_to_variable_heights: Dict,
        labels: Dict[str, Any],
        algebra: Union[AlgebraBackend, IntegrationBackend],
    ):
        self.domain = domain
        self.literals = literals
        self.node_to_variable_heights = node_to_variable_heights
        self.labels = labels
        self.algebra = algebra
        self.hits = 0
        self.misses = 0

    def node_to_variables(self, node_id):
        return set(self.node_to_variable_heights[node_id].keys())

    def recursive(self, weight_list, node, variables, cache=None):
        if cache is None:
            cache = dict()

        key = (node, frozenset(variables))
        if key in cache:
            self.hits += 1
            return cache[key]
        else:
            self.misses += 1

        if node.is_false():
            result = self.walk_false()
            cache[key] = result
            return result
        if node.is_true():
            result = self.walk_true()
            cache[key] = result
            return result

        if node.is_decision():
            result = self.algebra.zero()
            for prime, sub in node.elements():
                result = self.algebra.plus(
                    result, self.walk_and(weight_list, prime, sub, variables, cache),
                )
        else:
            result = self.walk_literal(weight_list, node, variables)

        cache[key] = result

        return result

    def walk_true(self):
        return self.algebra.one()

    def walk_false(self):
        return self.algebra.zero()

    def walk_and(self, weight_list, prime, sub, variables, cache):
        if prime.is_false() or sub.is_false():
            return self.algebra.zero()

        variables_prime_up = self.node_to_variables(prime.id) & variables
        variables_sub_up = self.node_to_variables(sub.id) & variables
        variables_shared_up = variables_prime_up & variables_sub_up
        # print(variables_shared_up)

        variables_prime_weight = set()
        variables_sub_weight = set()

        groups = self.get_variable_groups(weight_list, exclude=variables_shared_up)
        for g in groups:
            height_prime = self.group_to_height(prime.id, g, aggregate=sum)
            height_sub = self.group_to_height(sub.id, g, aggregate=sum)
            if height_prime > height_sub:
                variables_prime_weight |= g
            else:
                variables_sub_weight |= g

        variables_prime_to_sub = variables_prime_up & variables_sub_weight
        variables_sub_to_prime = variables_sub_up & variables_prime_weight

        weight_here_up = []
        weight_here_weight = []
        weight_sub_down = []
        weight_prime_down = []

        for w in weight_list:
            w_var = set(map(str, w.variables)) & variables
            # print(w)
            # print(w_var)

            # print(variables_prime_up, "prime_up")
            # print(variables_sub_up, "sub_up")
            # print(variables_prime_weight, "prime_down")
            # print(variables_sub_weight, "sub_down")

            if w_var <= variables_shared_up:
                weight_here_up.append(w)
            elif w_var <= variables_prime_to_sub:
                weight_here_weight.append(w)
            elif w_var <= variables_sub_to_prime:
                weight_here_weight.append(w)
            elif w_var <= variables_prime_up | variables_sub_to_prime:
                weight_prime_down.append(w)
            elif w_var <= variables_sub_up | variables_prime_to_sub:
                weight_sub_down.append(w)
            else:
                raise TypeError

        # print("")
        # print(weight_list)
        # print(weight_prime_down)
        # print(weight_sub_down)
        # print(weight_here_up)
        # print(weight_here_weight)

        # print(variables_prime_down)
        # print(variables_sub_down)

        variables_prime_down = variables_prime_up - (
            variables_shared_up | variables_prime_to_sub
        )
        variables_sub_down = variables_sub_up - (
            variables_shared_up | variables_sub_to_prime
        )

        prime_result = self.recursive(
            weight_prime_down, prime, variables_prime_down, cache,
        )
        sub_result = self.recursive(weight_sub_down, sub, variables_sub_down, cache,)

        # print("")
        # print(weight_list)
        # print(variables)
        # print(variables_shared_up, "shared_up")
        # print(variables_prime_to_sub, "prime_to_sub")
        # print(variables_sub_to_prime, "sub_to_prime")

        # print(weight_here_up, "weight_here_up")
        # print(weight_here_weight, "weight_here_weight")
        # print(weight_sub_down, "weight_sub_down")
        # print(weight_prime_down, "weight_prime_down")

        result = self.algebra.times(prime_result, sub_result)

        # print("")
        # print(variables)
        # print(weight_list)

        variables_weight_here_weight = variables_prime_to_sub | variables_sub_to_prime

        # print(variables_weight_here_weight, "var weight_here_weight")
        if variables_weight_here_weight:
            w = reduce(operator.mul, weight_here_weight)
            w = self.algebra.symbolic_weight(w)
            result = self.algebra.times(result, w)
            result = self.algebra.integrate(
                self.domain, result, variables_weight_here_weight
            )

        # print(variables_shared_up)
        # print(weight_list)
        # print(variables_shared_up, "var shared up")
        if variables_shared_up:
            w = reduce(
                operator.mul, weight_here_up, self.algebra.symbolic_backend.one()
            )
            # print(w)
            # print(result)
            w = self.algebra.symbolic_weight(w)
            w = self.algebra.times(result, w)

            result = self.algebra.integrate(self.domain, result, variables_shared_up)
            # print(result)
        # print(result)
        return result

    def walk_literal(self, weight_list, node, variables):
        literal = node.literal
        var = self.literals.inv_numbered[abs(literal)]  # var as abstracted in SDD
        abstraction = self.literals[var]
        if isinstance(abstraction, str):
            if abstraction in self.labels:
                expr = Polynomial.from_smt(
                    self.labels[abstraction][0 if (literal > 0) else 1]
                ).to_expression(self.algebra)
            else:
                expr = self.algebra.one()
        else:
            if literal < 0:
                abstraction = ~abstraction
            # expr = LinearInequality.from_smt(f).scale_to_integer().to_expression(self.algebra)
            expr = self.algebra.parse_condition(abstraction)

        weight = self.algebra.one()
        for w in weight_list:
            weight = self.algebra.times(weight, self.algebra.symbolic_weight(w))
        expr = self.algebra.times(weight, expr)

        if variables:
            return self.algebra.integrate(self.domain, expr, variables)
        else:
            return expr

    def get_variable_groups(self, weight_list, exclude=set()):
        groups = [
            set(map(str, w.variables)) - exclude
            for w in weight_list
            if set(map(str, w.variables)) - exclude
        ]
        return self._get_variable_groups(groups)

    def _get_variable_groups(self, groups):
        for i, v in enumerate(groups):
            for j, k in enumerate(groups[i + 1 :], i + 1):
                if v & k:
                    groups[i] = v.union(groups.pop(j))
                    return self._get_variable_groups(groups)
        return groups

    def group_to_height(self, node, group, aggregate=sum):
        # print(self.node_to_variable_heights[node])
        heights = [self.node_to_variable_heights[node].get(str(v), 0) for v in group]
        if heights:
            return aggregate(heights)
        else:
            return 0

    # def integrate(self, expr, variables):
    #     # type: (Any, Iterable[int]) -> Any
    #     result = expr
    #     variables, poly = self.groups[group_id]
    #         group_expr = self.algebra.times(result, poly.to_expression(self.algebra))
    #         if logger.isEnabledFor(logging.DEBUG):
    #             logger.debug("%s: %s", variables, str(group_expr))
    #         result = self.algebra.integrate(self.domain, group_expr, variables)
    #     return result


class FactorizedXsddEngine(BaseXsddEngine):
    def __init__(
        self,
        domain,
        support,
        weight,
        algebra: Optional[IntegratorAndAlgebra] = None,
        **kwargs
    ):
        algebra = algebra or PSIAlgebra()
        super().__init__(
            domain, support, weight, algebra.exact, algebra=algebra, **kwargs
        )

    def copy(self, domain, support, weight, **kwargs):
        return super().copy(domain, support, weight, self.algebra.exact, **kwargs)

    def get_weight_algebra(self):
        if True:
            return PolynomialAlgebra()
        else:
            return FactorizedPolynomialAlgebra()

    def get_labels_and_weight(self):
        return extract_labels_and_weight(self.weight)

    def compute_volume_from_pieces(
        self, base_support, piecewise_function, labeling_dict
    ):
        weights_dict = {
            pice_weight: piece_support & base_support
            for pice_weight, piece_support in piecewise_function.pieces.items()
        }

        volume = self.algebra.zero()

        for i, (weight, support) in enumerate(weights_dict.items()):
            logger.debug("----- Term %s -----", weight)

            repl_env, logic_support, literals = extract_and_replace_literals(support)
            literals.labels = labeling_dict

            vtree = self.get_vtree(support, literals)
            support_sdd = self.get_sdd(logic_support, literals, vtree)

            # from psipy import S, Polynomial

            subvolume = self.compute_volume_for_piece(weight, literals, support_sdd)
            # node = self.algebra.pool.get_node(subvolume)
            # print((node.expression * Polynomial(S(1.0))).simplify())
            volume = self.algebra.plus(volume, subvolume)
        return volume

    def compute_volume_for_piece(self, weight, literals: LiteralInfo, support_sdd):

        literal_to_variables = dict()
        # From here, we will use numbered literals instead of the normal named ones
        for inequality, literal in literals.abstractions.items():
            lit_num = literals.numbered[literal]
            inequality_variables = LinearInequality.from_smt(inequality).variables
            literal_to_variables[lit_num] = inequality_variables
            literal_to_variables[-lit_num] = inequality_variables

        for var, (true_label, false_label) in literals.labels.items():
            lit_num = literals.numbered[literals.booleans[var]]
            true_inequality_variables = set(
                [v for v in map(str, true_label.get_free_variables())]
            )
            false_inequality_variables = set(
                [v for v in map(str, false_label.get_free_variables())]
            )
            literal_to_variables[lit_num] = true_inequality_variables
            literal_to_variables[-lit_num] = false_inequality_variables

        tag_analysis = VariableTagAnalysis(literal_to_variables)

        walk(tag_analysis, support_sdd)
        node_to_variable_heights = tag_analysis.node_to_variable_heights

        variables = set(self.domain.real_vars)
        constant, weight_list = self._factorize_list(weight)

        from psipy import S

        print("")
        print(weight.simplify())
        print(constant)
        print((constant.to_PsiExpr() * S(1.0)).simplify())
        print(weight_list)

        integrator = FactorizedIntegrator(
            self.domain,
            literals,
            node_to_variable_heights,
            literals.labels,
            self.algebra,
        )

        expression = integrator.recursive(weight_list, support_sdd, variables)
        logger.debug("hits %s misses %s", integrator.hits, integrator.misses)

        bool_vars = amc(BooleanFinder(literals), support_sdd)
        missing_variable_count = len(self.domain.bool_vars) - len(bool_vars)
        bool_worlds = self.algebra.power(self.algebra.real(2), missing_variable_count)
        result_with_booleans = self.algebra.times(expression, bool_worlds)

        node = self.algebra.pool.get_node(result_with_booleans)
        print((node.expression.to_PsiExpr() * S(1.0)).simplify())
        # print(result.with)
        constant = self.algebra.symbolic_weight(constant)
        return self.algebra.times(constant, result_with_booleans)

    def _factorize_list(self, weight):
        # TODO do this without sympy (lot of work)

        import psipy
        import sympy

        if not weight.variables:
            return weight, []
        else:

            weight = weight.simplify()
            weight = psipy.toSympyString(weight)
            weight = weight.strip(",pZ,0,'+')").strip("limit(")

            weight = sympy.sympify(weight).as_poly()
            weight = sympy.factor_list(weight)

            def sympy2psi(expr):
                if type(expr) == sympy.Poly:
                    expr = expr.as_expr()

                if expr.is_constant() or expr.is_symbol:
                    return psipy.S(str(expr))

                elif expr.is_Pow:
                    b = sympy2psi(expr.args[0])
                    e = sympy2psi(expr.args[1])
                    return b ** e
                elif expr.is_Add:
                    args = [sympy2psi(a) for a in expr.args]
                    result = psipy.S(0)
                    for a in args:
                        result = result + a
                    return result.simplify()
                elif expr.is_Mul:
                    args = [sympy2psi(a) for a in expr.args]
                    result = psipy.S(1)
                    for a in args:
                        result = result * a
                    return result.simplify()

            constant = psipy.Polynomial(psipy.S(str(weight[0])))
            factor_list = []
            for f in weight[1]:
                factor_list.append(
                    psipy.Polynomial(sympy2psi(f[0]) ** psipy.S(f[1])).simplify()
                )

            return constant, factor_list

    def __str__(self):
        return "FXSDD" + super().__str__()
