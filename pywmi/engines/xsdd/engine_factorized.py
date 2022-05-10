from typing import Dict, Tuple, Set, Union, List, Optional, Any
import logging
from collections import defaultdict
from pywmi.engines.xsdd.smt_to_sdd import extract_labels_and_weight

import pysmt.shortcuts as smt

from pywmi import Domain
from pywmi.smt_math import PolynomialAlgebra, Polynomial, LinearInequality
from pywmi.engines.algebraic_backend import (
    AlgebraBackend,
    IntegrationBackend,
    PsiPiecewisePolynomialAlgebra,
    SympyAlgebra,
)
from pywmi.multimap import multimap

from .semiring import amc, Semiring, SddWalker, walk
from .engine import BaseXsddEngine, IntegratorAndAlgebra
from .literals import LiteralInfo, extract_and_replace_literals
from .smt_to_sdd import compile_to_sdd
from .draw import sdd_to_dot_file
from ...install import check_installation_psi
from ..pyxadd.algebra import PyXaddAlgebra

logger = logging.getLogger(__name__)


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


class FactorizedIntegrator:
    def __init__(
        self,
        domain: Domain,
        literals: LiteralInfo,
        groups: Dict[int, Tuple[Set[str], Polynomial]],
        node_to_groups: Dict,
        labels: Dict[str, Any],
        algebra: Union[AlgebraBackend, IntegrationBackend],
    ):
        self.domain = domain
        self.literals = literals
        self.groups = groups
        self.node_to_groups = node_to_groups
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
            result = self.walk_false()
            for prime, sub in node.elements():
                wa = self.walk_and(prime, sub, tags, cache, order)
                result = self.plus(result, wa)
        else:
            expression, variables = self.walk_literal(node)
            logger.debug("node LIT(%s)", node.id)
            result = (self.integrate(expression, tags), variables)

        cache[key] = result
        return result

    def plus(self, a, b):
        var_count_diff = len(a[1]) - len(b[1])
        if not var_count_diff:
            return self.algebra.plus(a[0], b[0]), a[1] | b[1]
        else:
            missing_a = len(b[1] - a[1])
            missing_b = len(a[1] - b[1])
            bool_worlds_a = self.algebra.power(self.algebra.real(2), missing_a)
            bool_worlds_b = self.algebra.power(self.algebra.real(2), missing_b)

            w_a = self.algebra.times(a[0], bool_worlds_a)
            w_b = self.algebra.times(b[0], bool_worlds_b)

            return self.algebra.plus(w_a, w_b), a[1] | b[1]

        return

    def walk_true(self):
        return self.algebra.one(), set()

    def walk_false(self):
        return self.algebra.zero(), set()

    def walk_and(self, prime, sub, tags, cache, order):

        if prime.is_false() or sub.is_false():
            return self.algebra.zero(), set()
        tags_prime = self.node_to_groups[prime.id] & tags
        tags_sub = self.node_to_groups[sub.id] & tags
        tags_shared = tags_prime & tags_sub
        if order and len(tags_shared) > 0:
            first_index = min(order.index(tag) for tag in tags_shared)
            tags_shared |= tags & set(order[first_index:])
        prime_result, variables_prime = self.recursive(
            prime, tags_prime - tags_shared, cache, order
        )
        sub_result, variables_sub = self.recursive(
            sub, tags_sub - tags_shared, cache, order
        )
        logger.debug("node AND(%s, %s)", prime.id, sub.id)
        result = self.integrate(
            self.algebra.times(prime_result, sub_result),
            [e for e in order if e in tags_shared] if order else tags_shared,
        )

        return result, variables_prime | variables_sub

    def walk_literal(self, node):
        literal = node.literal
        var = self.literals.inv_numbered[abs(literal)]  # var as abstracted in SDD
        abstraction = self.literals[var]
        if isinstance(abstraction, str):
            if abstraction in self.labels:
                expr = Polynomial.from_smt(
                    self.labels[abstraction][0 if (literal > 0) else 1]
                ).to_expression(self.algebra)
                bool_vars = {abstraction} if abstraction in self.literals.booleans else set()
                return expr, bool_vars
            else:
                return self.algebra.one(), {abstraction}
        else:
            #TODO: Can abstraction be a boolean? Do we need to pass expr, {abstraction} then?
            if literal < 0:
                abstraction = ~abstraction
            # expr = LinearInequality.from_smt(f).scale_to_integer().to_expression(self.algebra)
            expr = self.algebra.parse_condition(abstraction)
            return expr, set()

    def integrate(self, expr, tags):
        # type: (Any, Iterable[int]) -> Any
        result = expr
        for group_id in tags:
            variables, poly = self.groups[group_id]
            group_expr = self.algebra.times(result, poly.to_expression(self.algebra))
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
        if algebra is None:
            if check_installation_psi():
                algebra = PsiPiecewisePolynomialAlgebra()
            else:
                algebra = PyXaddAlgebra(symbolic_backend=SympyAlgebra())

        super().__init__(
            domain, support, weight, algebra.exact, algebra=algebra, **kwargs
        )

    def copy(self, domain, support, weight, **kwargs):
        return super().copy(domain, support, weight, self.algebra.exact, **kwargs)

    def get_weight_algebra(self):
        return PolynomialAlgebra()

    def get_labels_and_weight(self):
        return extract_labels_and_weight(self.weight)

    def compute_volume_from_pieces(
        self, base_support, piecewise_function, labeling_dict
    ):
        # Prepare the support for each piece (not compiled yet)
        term_supports = multimap()
        for piece_weight, piece_support in piecewise_function.pieces.items():
            logger.debug(
                "piece with weight %s and support %s", piece_weight, piece_support
            )
            for term in piece_weight.get_terms():
                term_supports[term].add(piece_support)

        terms_dict = {
            term: smt.Or(*supports) & base_support
            for term, supports in term_supports.items()
        }

        volume = self.algebra.zero()

        for i, (term, support) in enumerate(terms_dict.items()):
            logger.debug("----- Term %s -----", term)

            repl_env, logic_support, literals = extract_and_replace_literals(support)
            literals.labels = labeling_dict

            vtree = self.get_vtree(support, literals)
            support_sdd = self.get_sdd(logic_support, literals, vtree)

            # TODO
            # if logger.getEffectiveLevel() == logging.DEBUG:
            #    filename = f"sdd_{i}.dot"
            #    sdd_to_dot_file(support_sdd, literals, filename, node_to_groups)
            #    logger.debug(f"saved SDD of piece {i} to {filename}")

            subvolume = self.compute_volume_for_piece(term, literals, support_sdd)
            volume = self.algebra.plus(volume, subvolume)
        return volume

    def compute_volume_for_piece(self, term, literals: LiteralInfo, support_sdd):
        variable_groups = self.get_variable_groups_poly(term, self.domain.real_vars)

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
            literals.labels,
            self.algebra,
        )
        logger.debug("group order %s", group_order)
        expression, variables = integrator.recursive(support_sdd, order=group_order)
        # expression = integrator.integrate(expression, node_to_groups[support.id])
        logger.debug("hits %s misses %s", integrator.hits, integrator.misses)
        missing_variable_count = len(self.domain.bool_vars) - len(variables)
        bool_worlds = self.algebra.power(self.algebra.real(2), missing_variable_count)
        result_with_booleans = self.algebra.times(expression, bool_worlds)
        if len(constant_group_indices) == 1:
            constant_poly = group_to_vars_poly[constant_group_indices[0]][1]
            constant = constant_poly.to_expression(self.algebra)
        elif len(constant_group_indices) == 0:
            constant = self.algebra.one()
        else:
            raise ValueError(
                "Multiple constant groups: {}".format(constant_group_indices)
            )
        return self.algebra.times(constant, result_with_booleans)

    @classmethod
    def get_variable_groups_poly(
        cls, weight: Polynomial, real_vars: List[str]
    ) -> List[Tuple[Set[str], Polynomial]]:

        if isinstance(weight, Polynomial):
            if len(real_vars) > 0:
                result = []
                found_vars = weight.variables
                for v in real_vars:
                    if v not in found_vars:
                        result.append(({v}, Polynomial.from_constant(1)))
                return result + cls.get_variable_groups_poly(weight, [])

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
                            result[frozenset((v,))] *= Polynomial.from_smt(
                                smt.Symbol(v, smt.REAL)
                            )
                        result[frozenset()] *= Polynomial.from_constant(value)
                return list(result.items())
        else:
            raise NotImplementedError

    def __str__(self):
        return "FXSDD" + super().__str__()
