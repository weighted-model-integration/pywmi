from typing import Dict, Tuple, Set, Union, List, Optional, Any
import logging
import copy
from collections import defaultdict
from pywmi.engines.xsdd.smt_to_sdd import extract_labels_and_weight

import pysmt.shortcuts as smt

from pywmi import Domain
from pywmi.smt_math import PolynomialAlgebra, Polynomial, LinearInequality
from pywmi.engines.algebraic_backend import (
    AlgebraBackend,
    IntegrationBackend,
    PSIAlgebra,
)
from pywmi.multimap import multimap

from .semiring import amc, Semiring, SddWalker, walk
from .engine import BaseXsddEngine, IntegratorAndAlgebra
from .literals import LiteralInfo, extract_and_replace_literals
from .smt_to_sdd import compile_to_sdd
from .draw import sdd_to_dot_file
from .factorized_polynomial import FactorizedPolynomialAlgebra, FactorizedPolynomial

logger = logging.getLogger(__name__)


class VariableTagAnalysis(SddWalker):
    def __init__(self, literal_to_groups):
        # print(literal_to_groups)
        self.literal_to_groups = literal_to_groups
        self.node_to_groups = dict()
        self.node_to_variable_heights = dict()
        # print(literal_to_groups.values())
        # variabprint(set(l for ltg in literal_to_groups.values() for l in ltg))
        # self.variable_height = {key}

        # self.variable_height = {key: None for key in keyList}

    def walk_true(self, node):
        groups = set()
        variable_heights = {}
        self.node_to_groups[node.id] = groups
        self.node_to_variable_heights[node.id] = variable_heights
        return True, groups, variable_heights

    def walk_false(self, node):
        groups = set()
        variable_heights = {}
        self.node_to_groups[node.id] = groups
        self.node_to_variable_heights[node.id] = variable_heights
        return False, groups, variable_heights

    def walk_and(self, prime_result, sub_result, prime_node, sub_node):
        prime_feasible, prime_groups, prime_variable_heights = prime_result
        sub_feasible, sub_groups, sub_variable_heights = sub_result

        feasible = prime_feasible and sub_feasible
        groups = (prime_groups | sub_groups) if feasible else set()

        variable_heights = self._aggregate_heights(
            prime_variable_heights, sub_variable_heights
        )
        variable_heights = {k: v + 1 for k, v in variable_heights.items()}

        self.node_to_groups[(prime_node.id, sub_node.id)] = groups
        self.node_to_variable_heights[(prime_node.id, sub_node.id)] = variable_heights

        return feasible, groups, variable_heights

    def walk_or(self, child_results, node):
        feasible = any(t[0] for t in child_results)
        groups = set()
        variable_heights = {}
        if feasible:
            for _, child_groups, child_variable_heights in child_results:
                groups |= child_groups
                variable_heights = self._aggregate_heights(
                    variable_heights, child_variable_heights
                )
        self.node_to_groups[node.id] = groups
        self.node_to_variable_heights[node.id] = variable_heights

        return feasible, groups, variable_heights

    def walk_literal(self, l, node):
        groups = set(self.literal_to_groups.get(l, []))
        self.node_to_groups[node.id] = groups

        variable_heights = {v: 1 for v in groups}
        self.node_to_variable_heights[node.id] = variable_heights
        return True, groups, variable_heights

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
        groups: Dict[int, Tuple[Set[str], Polynomial]],
        node_to_groups: Dict,
        node_to_variable_heights: Dict,
        labels: Dict[str, Any],
        algebra: Union[AlgebraBackend, IntegrationBackend],
    ):
        self.domain = domain
        self.literals = literals
        self.groups = groups
        self.node_to_groups = node_to_groups
        self.node_to_variable_heights = node_to_variable_heights
        self.labels = labels
        self.algebra = algebra
        self.hits = 0
        self.misses = 0

    def recursive(self, node, tags=None, cache=None, order=None):
        if cache is None:
            cache = dict()

        if tags is None:
            tags = self.node_to_groups[node.id]

        key = (node, frozenset(tags))
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
                    result, self.walk_and(prime, sub, tags, cache, order)
                )
        else:
            expression = self.walk_literal(node)
            logger.debug("node LIT(%s)", node.id)
            result = self.integrate(expression, tags)

        cache[key] = result
        return result

    def walk_true(self):
        return self.algebra.one()

    def walk_false(self):
        return self.algebra.zero()

    def walk_and(self, prime, sub, tags, cache, order):
        if prime.is_false() or sub.is_false():
            return self.algebra.zero()
        tags_prime = self.node_to_groups[prime.id] & tags
        tags_sub = self.node_to_groups[sub.id] & tags
        tags_shared = tags_prime & tags_sub

        variable_heights_prime = self.node_to_variable_heights[prime.id]
        variable_heights_sub = self.node_to_variable_heights[sub.id]

        if order and len(tags_shared) > 0:
            first_index = min(order.index(tag) for tag in tags_shared)
            tags_shared |= tags & set(order[first_index:])

        prime_result = self.recursive(prime, tags_prime - tags_shared, cache, order)
        sub_result = self.recursive(sub, tags_sub - tags_shared, cache, order)
        logger.debug("node AND(%s, %s)", prime.id, sub.id)
        return self.integrate(
            self.algebra.times(prime_result, sub_result),
            [e for e in order if e in tags_shared] if order else tags_shared,
        )

    def walk_literal(self, node):
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

        return expr

    def integrate(self, expr, tags):
        # type: (Any, Iterable[int]) -> Any
        result = expr
        for group_id in tags:
            variables, poly = self.groups[group_id]
            group_expr = self.algebra.times(result, self.algebra.symbolic_weight(poly))
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("%s: %s", variables, str(group_expr))
            result = self.algebra.integrate(self.domain, group_expr, variables)
        return result


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
        # Prepare the support for each piece (not compiled yet)
        # term_supports = multimap()
        # for piece_weight, piece_support in piecewise_function.pieces.items():

        #     print(piece_weight)
        #     print(piece_support)
        #     for term in piece_weight.get_terms():
        #         term_supports[term].add(piece_support)

        # terms_dict = {
        #     term: smt.Or(*supports) & base_support
        #     for term, supports in term_supports.items()
        # }

        # for w, s in piecewise_function.pieces.items():
        #     print(w)
        #     print(s)

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

            # TODO
            # if logger.getEffectiveLevel() == logging.DEBUG:
            #    filename = f"sdd_{i}.dot"
            #    sdd_to_dot_file(support_sdd, literals, filename, node_to_groups)
            #    logger.debug(f"saved SDD of piece {i} to {filename}")

            subvolume = self.compute_volume_for_piece(weight, literals, support_sdd)

            volume = self.algebra.plus(volume, subvolume)
        return volume

    def compute_volume_for_piece(self, weight, literals: LiteralInfo, support_sdd):
        variable_groups = self.get_variable_groups_poly(weight, self.domain.real_vars)

        if self.ordered:
            sort_key = (
                lambda t: max(self.domain.real_vars.index(v) for v in t[1][0])
                if len(t[1][0]) > 0
                else -1
            )
            group_order = [
                t[0]
                for t in sorted(enumerate(variable_groups), key=sort_key, reverse=False)
            ]
            logger.debug("variable groups %s", variable_groups)
            logger.debug("group order %s", group_order)
            logger.debug("real variables %s", self.domain.real_vars)
        else:
            group_order = None

        def get_group(_v):
            for i, (_vars, _node) in enumerate(variable_groups):
                if _v in _vars:
                    return i
            raise ValueError(
                "Variable {} not found in any group ({})".format(_v, variable_groups)
            )

        literal_to_groups = dict()
        # From here, we will use numbered literals instead of the normal named ones
        for inequality, literal in literals.abstractions.items():
            lit_num = literals.numbered[literal]
            inequality_variables = LinearInequality.from_smt(inequality).variables
            inequality_groups = [get_group(v) for v in inequality_variables]
            literal_to_groups[lit_num] = inequality_groups
            literal_to_groups[-lit_num] = inequality_groups

        for var, (true_label, false_label) in literals.labels.items():
            lit_num = literals.numbered[literals.booleans[var]]
            true_inequality_groups = [
                get_group(v) for v in map(str, true_label.get_free_variables())
            ]
            false_inequality_groups = [
                get_group(v) for v in map(str, false_label.get_free_variables())
            ]
            literal_to_groups[lit_num] = true_inequality_groups
            literal_to_groups[-lit_num] = false_inequality_groups

        # for var, (true_label, false_label) in labels.items():
        #    true_inequality_groups = [get_group(v) for v in map(str, true_label.get_free_variables())]
        #    false_inequality_groups = [get_group(v) for v in map(str, false_label.get_free_variables())]
        #    literal_to_groups[var_to_lit[var]] = true_inequality_groups
        #    literal_to_groups[-var_to_lit[var]] = false_inequality_groups

        tag_analysis = VariableTagAnalysis(literal_to_groups)
        walk(tag_analysis, support_sdd)
        node_to_groups = tag_analysis.node_to_groups
        node_to_variable_heights = tag_analysis.node_to_variable_heights

        group_to_vars_poly = {i: g for i, g in enumerate(variable_groups)}
        # all_groups = frozenset(i for i, e in group_to_vars_poly.items() if len(e[0]) > 0)

        constant_group_indices = [
            i for i, e in group_to_vars_poly.items() if len(e[0]) == 0
        ]
        integrator = FactorizedIntegrator(
            self.domain,
            literals,
            group_to_vars_poly,
            node_to_groups,
            node_to_variable_heights,
            literals.labels,
            self.algebra,
        )
        logger.debug("group order %s", group_order)
        expression = integrator.recursive(support_sdd, order=group_order)
        # expression = integrator.integrate(expression, node_to_groups[support.id])
        logger.debug("hits %s misses %s", integrator.hits, integrator.misses)
        bool_vars = amc(BooleanFinder(literals), support_sdd)
        missing_variable_count = len(self.domain.bool_vars) - len(bool_vars)
        bool_worlds = self.algebra.power(self.algebra.real(2), missing_variable_count)
        result_with_booleans = self.algebra.times(expression, bool_worlds)
        if len(constant_group_indices) == 1:
            constant_poly = group_to_vars_poly[constant_group_indices[0]][1]
            constant = self.algebra.symbolic_weight(constant_poly)
            # constant = constant_poly.to_expression(self.algebra)
        elif len(constant_group_indices) == 0:
            constant = self.algebra.one()
        else:
            raise ValueError(
                "Multiple constant groups: {}".format(constant_group_indices)
            )
        return self.algebra.times(constant, result_with_booleans)

    def get_variable_groups_poly(
        self, weight: Polynomial, real_vars: List[str],
    ) -> List[Tuple[Set[str], Polynomial]]:
        from psipy import Polynomial as PsiPolynomial

        if isinstance(weight, PsiPolynomial):
            if len(real_vars) > 0:
                result = []
                found_vars = [str(v) for v in weight.variables]
                for v in real_vars:
                    if v not in found_vars:
                        result.append(
                            (
                                {v},
                                PsiPolynomial(
                                    self.algebra.symbolic_backend.symbol("1")
                                ),
                            )
                        )
                return result + self.get_variable_groups_poly(weight, [])

            factors = weight.factorize_list()
            return [(set([str(v) for v in f.variables]), f) for f in factors]
        else:
            raise NotImplementedError

    def __str__(self):
        return "FXSDD" + super().__str__()