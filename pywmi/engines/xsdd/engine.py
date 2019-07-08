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


class FactorizedIntegrator:
    def __init__(self,
                 domain: Domain,
                 abstractions: Dict,
                 var_to_lit: Dict,
                 groups: Dict[int, Tuple[Set[str], Polynomial]],
                 node_to_groups: Dict,
                 labels: Dict,
                 algebra: Union[AlgebraBackend, IntegrationBackend]) -> None:
        self.domain = domain
        self.reverse_abstractions = {v: k for k, v in abstractions.items()}
        self.lit_to_var = {v: k for k, v in var_to_lit.items()}
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
            result = self.algebra.zero()
            for prime, sub in node.elements():
                result = self.algebra.plus(result, self.walk_and(prime, sub, tags, cache, order))
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
        if order and len(tags_shared) > 0:
            first_index = min(order.index(tag) for tag in tags_shared)
            tags_shared |= (tags & set(order[first_index:]))
        prime_result = self.recursive(prime, tags_prime - tags_shared, cache, order)
        sub_result = self.recursive(sub, tags_sub - tags_shared, cache, order)
        logger.debug("node AND(%s, %s)", prime.id, sub.id)
        return self.integrate(self.algebra.times(prime_result, sub_result),
                              [e for e in order if e in tags_shared] if order else tags_shared)

    def walk_literal(self, node):
        literal = node.literal
        if abs(literal) in self.lit_to_var:
            var = self.lit_to_var[abs(literal)]
            if var in self.labels:
                expr = Polynomial.from_smt(self.labels[var][0 if (literal > 0) else 1]).to_expression(self.algebra)
            else:
                expr = self.algebra.one()
        else:
            f = self.reverse_abstractions[abs(literal)]
            if literal < 0:
                f = ~f
            # expr = LinearInequality.from_smt(f).scale_to_integer().to_expression(self.algebra)
            expr = self.algebra.parse_condition(f)

        return expr

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


class XsddEngine(Engine):
    def __init__(
            self,
            domain,
            support,
            weight,
            convex_backend: Optional[ConvexIntegrationBackend] = None,
            factorized=False,
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
        self.factorized = factorized
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

        algebra = PolynomialAlgebra()
        support = (smt.And(*self.collect_conflicts()) & self.support) if self.find_conflicts else self.support
        if self.factorized:
            labels, weight = extract_labels_and_weight(self.weight)
            logger.debug("Weight %s", self.weight)
            logger.debug("Labels %s", labels)
            logger.debug("New weight %s", weight)
        else:
            labels, weight = None, self.weight

        support_sdd = convert_formula(support, self.manager, algebra, abstractions, var_to_lit)
        piecewise_function = convert_function(weight, self.manager, algebra, abstractions, var_to_lit)

        if self.balance:
            self.manager = get_new_manager(self.domain, abstractions, var_to_lit, self.balance)
            support_sdd = convert_formula(support, self.manager, algebra, abstractions, var_to_lit)
            piecewise_function = convert_function(weight, self.manager, algebra, abstractions, var_to_lit)

        factorized_algebra = self.algebra
        if factorized_algebra is not None and isinstance(factorized_algebra, PyXaddAlgebra):
            # TODO Booleans in order?
            for test, lit in sorted(abstractions.items(), key=lambda t: t[1]):
                factorized_algebra.pool.bool_test(Decision(test))

        volume = factorized_algebra.zero()
        if self.factorized:
            terms_dict = dict()
            for w_weight, world_support in piecewise_function.sdd_dict.items():
                logger.debug("ww %s", w_weight)
                support = world_support
                for term in w_weight.get_terms():
                    if term in terms_dict:
                        terms_dict[term] = self.manager.disjoin(terms_dict[term], support)
                    else:
                        terms_dict[term] = support

            for key in terms_dict:
                terms_dict[key] = support_sdd & terms_dict[key]

            for support in terms_dict.values():
                support.ref()

            if self.minimize:
                self.manager.minimize()

            index = 0
            for term, support in terms_dict.items():
                logger.debug("term %s", term)
                # TODO BOOLEAN WORLDS

                variable_groups = self.get_variable_groups_poly(term, self.domain.real_vars)

                if self.ordered:
                    sort_key = lambda t: max(self.domain.real_vars.index(v)
                                             for v in t[1][0]) if len(t[1][0]) > 0 else -1
                    group_order = [t[0] for t in sorted(enumerate(variable_groups), key=sort_key, reverse=False)]
                    logger.debug("variable groups %s", variable_groups)
                    logger.debug("group order %s", group_order)
                    logger.debug("real variables %s", self.domain.real_vars)
                else:
                    group_order = None

                def get_group(_v):
                    for i, (_vars, _node) in enumerate(variable_groups):
                        if _v in _vars:
                            return i
                    raise ValueError("Variable {} not found in any group ({})".format(_v, variable_groups))

                literal_to_groups = dict()
                for inequality, literal in abstractions.items():
                    inequality_variables = LinearInequality.from_smt(inequality).variables
                    inequality_groups = [get_group(v) for v in inequality_variables]
                    literal_to_groups[literal] = inequality_groups
                    literal_to_groups[-literal] = inequality_groups

                for var, (true_label, false_label) in labels.items():
                    true_inequality_groups = [get_group(v) for v in map(str, true_label.get_free_variables())]
                    false_inequality_groups = [get_group(v) for v in map(str, false_label.get_free_variables())]
                    literal_to_groups[var_to_lit[var]] = true_inequality_groups
                    literal_to_groups[-var_to_lit[var]] = false_inequality_groups

                tag_analysis = VariableTagAnalysis(literal_to_groups)
                walk(tag_analysis, support)
                node_to_groups = tag_analysis.node_to_groups
                if logger.isEnabledFor(logging.DEBUG):
                    sdd_to_png_file(support, abstractions, var_to_lit, "exported_{}".format(index), node_to_groups)
                index += 1

                group_to_vars_poly = {i: g for i, g in enumerate(variable_groups)}
                # all_groups = frozenset(i for i, e in group_to_vars_poly.items() if len(e[0]) > 0)

                constant_group_indices = [i for i, e in group_to_vars_poly.items() if len(e[0]) == 0]
                integrator = FactorizedIntegrator(self.domain, abstractions, var_to_lit, group_to_vars_poly,
                                                  node_to_groups, labels, factorized_algebra)
                logger.debug("group order %s", group_order)
                expression = integrator.recursive(support, order=group_order)
                # expression = integrator.integrate(expression, node_to_groups[support.id])
                logger.debug("hits %s misses %s", integrator.hits, integrator.misses)
                bool_vars = amc(BooleanFinder(abstractions, var_to_lit), support)
                missing_variable_count = len(self.domain.bool_vars) - len(bool_vars)
                bool_worlds = factorized_algebra.power(factorized_algebra.real(2), missing_variable_count)
                result_with_booleans = factorized_algebra.times(expression, bool_worlds)
                if len(constant_group_indices) == 1:
                    constant_poly = group_to_vars_poly[constant_group_indices[0]][1]
                    constant = constant_poly.to_expression(factorized_algebra)
                elif len(constant_group_indices) == 0:
                    constant = factorized_algebra.one()
                else:
                    raise ValueError("Multiple constant groups: {}".format(constant_group_indices))
                result = factorized_algebra.times(constant, result_with_booleans)
                volume = factorized_algebra.plus(volume, result)

            for support in terms_dict.values():
                support.deref()
        else:
            for w_weight, world_support in piecewise_function.sdd_dict.items():
                support = support_sdd & world_support
                if not self.backend:
                    semiring = NonConvexWMISemiring(factorized_algebra, abstractions, var_to_lit)
                    expression, variables = amc(semiring, support)
                    expression = factorized_algebra.times(expression, w_weight.to_expression(factorized_algebra))
                    volume = factorized_algebra.integrate(self.domain, expression, self.domain.real_vars)

                    missing_variable_count = len(self.domain.bool_vars) - len(variables)
                    bool_worlds = factorized_algebra.power(factorized_algebra.real(2), missing_variable_count)
                    volume = factorized_algebra.times(volume, bool_worlds)
                else:
                    convex_supports = amc(ConvexWMISemiring(abstractions, var_to_lit), support)
                    logger.debug("#convex regions %s", len(convex_supports))
                    for convex_support, variables in convex_supports:
                        missing_variable_count = len(self.domain.bool_vars) - len(variables)
                        vol = self.integrate_convex(convex_support, w_weight.to_smt()) * 2 ** missing_variable_count
                        volume = factorized_algebra.plus(volume, factorized_algebra.real(vol))
        return factorized_algebra.to_float(volume)

    def copy(self, domain, support, weight):
        return XsddEngine(
            domain,
            support,
            weight,
            self.backend,
            self.factorized,
            self.manager,
            self.algebra,
            self.find_conflicts,
            self.ordered,
            self.balance,
            self.minimize
        )

    def __str__(self):
        solver_string = "xsdd:b{}".format(self.backend)
        if self.factorized:
            solver_string += ":factorized"
        if self.find_conflicts:
            solver_string += ":prune"
        if self.ordered:
            solver_string += ":order"
        if self.balance:
            solver_string += ":v{}".format(self.balance)
        if self.minimize:
            solver_string += ":minimize"
        return solver_string
