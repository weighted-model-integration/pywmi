import time
from collections import defaultdict
from functools import reduce
from typing import Dict, List, Tuple, Set, Union, Any, Optional

from pysmt.fnode import FNode
from typing import Iterable

from pywmi.engines.xsdd.vtree import get_new_manager
from pywmi.engines.xsdd.draw import sdd_to_dot_file, sdd_to_png_file
from pywmi.engines.algebraic_backend import AlgebraBackend, IntegrationBackend
from pywmi.engines.convex_integrator import ConvexIntegrationBackend
from pywmi.engines.algebraic_backend import StringAlgebra, XaddAlgebra, PSIAlgebra

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

import pysmt.shortcuts as smt

IntegratorAndAlgebra = Union[AlgebraBackend, IntegrationBackend]




class ContinuousProvenanceSemiring(Semiring):
    def __init__(self, abstractions: Dict, var_to_lit: Dict):
        self.reverse_abstractions = {v: k for k, v in abstractions.items()}
        self.lit_to_var = {v: k for k, v in var_to_lit.items()}
        self.index_to_conprov = {}

    def times_neutral(self):
        return (set(), set())

    def plus_neutral(self):
        return (set(), set())

    def plus(self, a, b, index=None):
        assert index
        variables = a[0] | b[0]
        common_variables_children = a[0] & b[0]
        result = (variables, common_variables_children)
        self.index_to_conprov[index] = result
        return result

    def times(self, a, b, index=None):
        assert index
        variables = a[0] | b[0]
        common_variables_children = a[0] & b[0]
        result = (variables, common_variables_children)
        self.index_to_conprov[index] = result
        return result

    def negate(self, a):
        raise NotImplementedError()

    def weight(self, a):
        if abs(a) in self.lit_to_var:
            variables = {self.lit_to_var[abs(a)]}
            self.index_to_conprov[a] = variables
            return (variables, variables)
        else:
            return (set(), set())

    def positive_weight(self, a):
        raise NotImplementedError()


class ParentAnalysis(SddWalker):
    def __init__(self, abstractions: Dict, var_to_lit: Dict):
        self.reverse_abstractions = {v: k for k, v in abstractions.items()}
        self.lit_to_var = {v: k for k, v in var_to_lit.items()}
        self.parents = defaultdict(lambda: [])

    def walk_true(self, node):
        return node.id

    def walk_false(self, node):
        return node.id

    def walk_and(self, prime_result, sub_result, prime, sub):
        node_id = (prime.id, sub.id)
        if prime_result:
            self.parents[prime_result].append(node_id)
        if sub_result:
            self.parents[sub_result].append(node_id)
        return node_id

    def walk_or(self, child_results, node):
        for result in child_results:
            if result:
                self.parents[result].append(node.id)
        return node.id

    def walk_literal(self, a, node):
        return node.id

    @staticmethod
    def get_parents(abstractions: Dict, var_to_lit: Dict, sdd: SddNode) -> Dict:
        analysis = ParentAnalysis(abstractions, var_to_lit)
        walk(analysis, sdd)
        return dict(analysis.parents)

    @staticmethod
    def get_children(abstractions: Dict, var_to_lit: Dict, sdd: SddNode) -> Dict:
        parent_dict = ParentAnalysis.get_parents(abstractions, var_to_lit, sdd)
        children = defaultdict(lambda: set())
        for child, parents in parent_dict.items():
            for parent in parents:
                children[parent].add(child)
        return {p: sorted(c) for p, c in children.items()}


class VariableTagAnalysis(SddWalker):
    def __init__(self, literal_to_groups):
        self.literal_to_groups = literal_to_groups
        self.node_to_groups = dict()

    def walk_true(self, node):
        # print(node.id, node)
        groups = set()
        self.node_to_groups[node.id] = groups
        return groups

    def walk_false(self, node):
        # print(node.id, node)
        groups = set()
        self.node_to_groups[node.id] = groups
        return groups

    def walk_and(self, prime_result, sub_result, prime_node, sub_node):
        # print((prime_node.id, sub_node.id), prime_node, sub_node)
        groups = prime_result | sub_result
        self.node_to_groups[(prime_node.id, sub_node.id)] = groups
        return groups

    def walk_or(self, child_results, node):
        # print(node.id, node)
        groups = reduce(lambda x, y: x | y, child_results, set())
        self.node_to_groups[node.id] = groups
        return groups

    def walk_literal(self, l, node):
        # print(node.id, node)
        groups = set(self.literal_to_groups.get(l, []))
        self.node_to_groups[node.id] = groups
        return groups


class IntTagSemiring(Semiring):
    def __init__(self, abstractions: Dict, var_to_lit: Dict, index_to_conprov: Dict):
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
            variables = f.variables()  # TODO look up correct method
            return (variables, variables)

    def positive_weight(self, a):
        raise NotImplementedError()


class WMISemiringPint(WMISemiring):
    def __init__(self, abstractions: Dict, var_to_lit: Dict, int_tags: Dict):
        WMISemiring.__init__(abstractions, var_to_lit)
        self.int_tags = int_tags


class FactorizedWMIWalker(SddWalker):
    def __init__(self,
                 domain: Domain,
                 abstractions: Dict,
                 var_to_lit: Dict,
                 groups: Dict[int, Tuple[Set[str], Polynomial]],
                 dependency: Dict,
                 integration_tags: Dict,
                 algebra: Union[AlgebraBackend, IntegrationBackend]) -> None:
        self.domain = domain
        self.reverse_abstractions = {v: k for k, v in abstractions.items()}
        self.lit_to_var = {v: k for k, v in var_to_lit.items()}
        self.groups = groups
        self.dependency = dependency
        self.integration_tags = integration_tags
        self.algebra = algebra

    def walk_true(self, node):
        return node.id, {frozenset(): self.algebra.one()}, set()

    def walk_false(self, node):
        return node.id, {frozenset(): self.algebra.zero()}, set()

    def get_requested_tags(self, parent_id, child_id):
        return frozenset(self.dependency[parent_id][child_id]) if parent_id in self.dependency else frozenset()

    def get_integration_tags(self, key):
        result = self.integration_tags[key]
        # result = self.integration_tags.get(key, {frozenset()})
        # result.add(frozenset())
        return result

    def walk_and(self, prime_result, sub_result, prime_node, sub_node):
        key = (prime_node.id, sub_node.id)
        # print("+", "AND", key, prime_result, sub_result)
        prime_id, prime_result, prime_bool_vars = prime_result
        sub_id, sub_result, sub_bool_vars = sub_result
        prime_tags = self.get_requested_tags(key, prime_id)
        sub_tags = self.get_requested_tags(key, sub_id)
        print("prime", prime_id, prime_result)
        print("sub", sub_id, sub_result)
        expression = self.algebra.times(prime_result[prime_tags], sub_result[sub_tags])
        bool_vars = prime_bool_vars | sub_bool_vars
        own_tags = self.get_integration_tags(key)
        expr_dict = self.integrate(expression, own_tags)
        expr_dict = {k | prime_tags | sub_tags: v for k, v in expr_dict.items()}
        # print("-", "AND", key, expr_dict, bool_vars)
        return key, expr_dict, bool_vars

    def walk_or(self, child_results, node):
        # print("+", "OR", node.id, child_results)
        # print(" ", "OR", *[child_result[1] for child_result in child_results])
        results = []
        for child_result in child_results:
            try:
                results.append((child_result[1][self.get_requested_tags(node.id, child_result[0])], child_result[2]))
            except KeyError:
                pass
        # assert all(self.dependency[node.id][child_results[i][0]] == self.dependency[node.id][child_results[0][0]]
        #            for i in range(1, len(child_results)))
        result, bool_vars = results[0]
        for child_result, child_bool_vars in results[1:]:
            result = self.algebra.plus(result, child_result)
            bool_vars |= child_bool_vars
        expr_dict = {self.get_requested_tags(node.id, child_results[0][0]): result}
        # print("-", "OR", node.id, expr_dict, bool_vars)
        return node.id, expr_dict, bool_vars

    def walk_literal(self, l, node):
        # print("+", "LIT", node.id, l)

        if abs(l) in self.lit_to_var:
            expr, bool_vars = self.algebra.one(), {self.lit_to_var[abs(l)]}
        else:
            f = self.reverse_abstractions[abs(l)]
            if l < 0:
                f = ~f
            expr, bool_vars = LinearInequality.from_smt(f).to_expression(self.algebra), set()
        expr_dict = self.integrate(expr, self.get_integration_tags(node.id))
        # print("-", "LIT", node.id, expr_dict, bool_vars)
        return node.id, expr_dict, bool_vars

    def integrate(self, expr, tags_set):
        # type: (Any, Set[Set[int]]) -> Dict[Set[int], Any]
        # print("+", "INT", expr, list(tags_set))
        result = dict()
        for group_tags in tags_set:
            tags_result = expr
            for group_id in group_tags:
                variables, poly = self.groups[group_id]
                group_expr = self.algebra.times(tags_result, poly.to_expression(self.algebra))
                tags_result = self.algebra.integrate(self.domain, group_expr, variables)
            result[group_tags] = tags_result
        # print("-", "INT", result)
        return result


def get_variable_groups_poly(weight: Polynomial, real_vars: List[str]) -> List[Tuple[Set[str], Polynomial]]:
    if len(real_vars) > 0:
        result = []
        found_vars = weight.variables
        for v in real_vars:
            if v not in found_vars:
                result.append(({v}, Polynomial.from_constant(1)))
        return result + get_variable_groups_poly(weight, [])

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


def get_variable_groups(weight: FNode) -> List[Tuple[Set[str], FNode]]:
    if weight.is_symbol():
        return [({weight.symbol_name()}, weight)]
    elif weight.is_constant():
        return [(set(), weight)]
    elif weight.is_times():
        result = []
        for arg in weight.args():
            result += get_variable_groups(arg)
        return result
    else:
        return [({str(v) for v in weight.get_free_variables()}, weight)]


def tag_sdd(parent_to_children, node_to_groups, root_id):
    dependency = defaultdict(lambda: dict())
    integration_tags = defaultdict(lambda: set())
    push_bounds_down(parent_to_children, node_to_groups, root_id, dependency, integration_tags)
    return dict(dependency), dict(integration_tags)


def push_bounds_down(parent_to_children, node_to_groups, root_id, dependency, integration_tags, mode="OR", tags=None,
                     prefix=""):
    # type: (Dict, Dict, int, Dict, Dict, str, Set, str) -> None
    if tags is None:
        tags = node_to_groups[root_id]

    print(prefix, "Root", root_id, "with vars:", node_to_groups[root_id], "tags", tags)

    # if len(tags) == 0 or len(tags - node_to_groups[root_id]) != 0:
        # if len(tags - node_to_groups[root_id]) != 0:
        #     print(prefix, "Could not find tags {}".format(tags - node_to_groups[root_id]))
        # return

    if root_id not in parent_to_children:
        # print(prefix, "Leaf {}".format(root_id))
        integration_tags[root_id].add(frozenset(tags))
        return

    children = parent_to_children[root_id]
    if mode == "OR":
        for child in children:
            dependency[root_id][child] = tags
            # print(prefix, "[{}] Push tags {} to child {}".format(root_id, tags, child))
            push_bounds_down(parent_to_children, node_to_groups, child, dependency, integration_tags, "AND", tags,
                             prefix + " | ")
    else:
        groups1 = node_to_groups[children[0]]
        groups2 = node_to_groups[children[1]]
        shared = groups1 & groups2
        shared_tags = shared & tags
        # if len(shared_tags) > 0:
        integration_tags[root_id].add(frozenset(shared_tags))
        tags1 = (groups1 - shared) & tags
        tags2 = (groups2 - shared) & tags
        # print(prefix, "INT", shared & tags, "LEFT", tags1, "RIGHT", tags2)
        dependency[root_id][children[0]] = tags1
        dependency[root_id][children[1]] = tags2
        push_bounds_down(parent_to_children, node_to_groups, children[0], dependency, integration_tags, "OR", tags1,
                         prefix + " | ")
        push_bounds_down(parent_to_children, node_to_groups, children[1], dependency, integration_tags, "OR", tags2,
                         prefix + " | ")


class NativeXsddEngine(Engine):
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
            balance: Optional[str] = None):
        super().__init__(domain, support, weight, convex_backend.exact if convex_backend else algebra.exact)
        if SddManager is None:
            from pywmi.errors import InstallError
            raise InstallError("NativeXsddEngine requires the pysdd package")
        self.factorized = factorized
        self.manager = manager or SddManager()
        self.algebra = algebra or PSIAlgebra()
        self.backend = convex_backend
        self.find_conflicts = find_conflicts
        self.ordered = ordered
        self.balance = balance

    def get_samples(self, n):
        raise NotImplementedError()

    def integrate_convex(self, convex_support, polynomial_weight):
        try:
            domain = Domain(self.domain.real_vars, {v: REAL for v in self.domain.real_vars}, self.domain.var_domains)
            return self.backend.integrate(domain, BoundsWalker.get_inequalities(convex_support),
                                          Polynomial.from_smt(polynomial_weight))
        except ZeroDivisionError:
            return 0

    def compute_volume(self, add_bounds=True):
        if add_bounds:
            return self.with_constraint(self.domain.get_bounds()).compute_volume(False)

        abstractions, var_to_lit = dict(), dict()

        conflicts = []
        if self.find_conflicts:
            inequalities = list(BoundsWalker(True).walk_smt(self.support) | BoundsWalker(True).walk_smt(self.weight))
            for i in range(len(inequalities) - 1):
                for j in range(i + 1, len(inequalities)):
                    if inequalities[i].get_free_variables() == inequalities[j].get_free_variables():
                        # print(inequalities[i], inequalities[j])
                        # TODO Find conflicts
                        if implies(inequalities[i], inequalities[j]):
                            conflicts.append(smt.Implies(inequalities[i], inequalities[j]))
                            # print(inequalities[i], "=>", inequalities[j])
                        if implies(~inequalities[i], inequalities[j]):
                            conflicts.append(smt.Implies(~inequalities[i], inequalities[j]))
                            # print(~inequalities[i], "=>", inequalities[j])
                        if implies(inequalities[j], inequalities[i]):
                            conflicts.append(smt.Implies(inequalities[j], inequalities[i]))
                            # print(inequalities[j], "=>", inequalities[i])
                        if implies(~inequalities[j], inequalities[i]):
                            conflicts.append(smt.Implies(~inequalities[j], inequalities[i]))
                            # print(~inequalities[j], "=>", inequalities[i])

        algebra = PolynomialAlgebra()
        support = smt.And(*conflicts) & self.support
        labels, weight = extract_labels_and_weight(self.weight)
        print("Weight", self.weight)
        print("Labels", labels)
        print("New weight", weight)

        support_sdd = convert_formula(support, self.manager, algebra, abstractions, var_to_lit)
        piecewise_function = convert_function(weight, self.manager, algebra, abstractions, var_to_lit)

        if self.balance:
            self.manager = get_new_manager(self.domain, abstractions, var_to_lit, self.balance)
            support_sdd = convert_formula(support, self.manager, algebra, abstractions, var_to_lit)
            piecewise_function = convert_function(weight, self.manager, algebra, abstractions, var_to_lit)

        volume = self.algebra.zero()
        if self.factorized:
            terms_dict = dict()
            for w_weight, world_support in piecewise_function.sdd_dict.items():
                print("ww", w_weight)
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
            # self.manager.minimize()

            index = 0
            for term, support in terms_dict.items():
                print("term", term)
                # TODO BOOLEAN WORLDS

                # print(pretty_print(recover_formula(support, abstractions, var_to_lit, False)))
                # print(term)
                variable_groups = get_variable_groups_poly(term, self.domain.real_vars)

                if self.ordered:
                    sort_key = lambda t: max(self.domain.real_vars.index(v)
                                             for v in t[1][0]) if len(t[1][0]) > 0 else -1
                    group_order = [t[0] for t in sorted(enumerate(variable_groups), key=sort_key, reverse=False)]
                    print(variable_groups)
                    print(group_order)
                    print(self.domain.real_vars)
                else:
                    group_order = None

                def get_group(_v):
                    for i, (_vars, _node) in enumerate(variable_groups):
                        if _v in _vars:
                            return i
                    raise ValueError("Variable {} not found in any group ({})".format(_v, variable_groups))

                # print(variable_groups)
                # child_to_parents_mapping = ParentAnalysis.get_parents(abstractions, var_to_lit, support)
                parent_to_children_mapping = ParentAnalysis.get_children(abstractions, var_to_lit, support)

                # print()
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

                print(literal_to_groups)

                # print("Literal -> groups", literal_to_groups)

                tag_analysis = VariableTagAnalysis(literal_to_groups)
                walk(tag_analysis, support)
                node_to_groups = tag_analysis.node_to_groups
                sdd_to_png_file(support, abstractions, var_to_lit, "exported_{}".format(index), node_to_groups)
                # quit()
                index += 1

                group_to_vars_poly = {i: g for i, g in enumerate(variable_groups)}
                # print("Group to vars - poly", group_to_vars_poly)
                all_groups = frozenset(i for i, e in group_to_vars_poly.items() if len(e[0]) > 0)

                constant_group_indices = [i for i, e in group_to_vars_poly.items() if len(e[0]) == 0]
                integrator = FactorizedIntegrator(self.domain, abstractions, var_to_lit, group_to_vars_poly,
                                                  node_to_groups, labels, self.algebra)
                print("\n", group_order)
                expression = integrator.recursive(support, order=group_order)
                # expression = integrator.integrate(expression, node_to_groups[support.id])
                # print()
                # print("hits", integrator.hits, "misses", integrator.misses)
                missing_variable_count = len(self.domain.bool_vars) - len(self.domain.bool_vars)  # TODO - len(bool_vars)
                bool_worlds = self.algebra.power(self.algebra.real(2), missing_variable_count)
                result_with_booleans = self.algebra.times(expression, bool_worlds)
                if len(constant_group_indices) == 1:
                    constant_poly = group_to_vars_poly[constant_group_indices[0]][1]
                    constant = constant_poly.to_expression(self.algebra)
                elif len(constant_group_indices) == 0:
                    constant = self.algebra.one()
                else:
                    raise ValueError("Multiple constant groups: {}".format(constant_group_indices))
                result = self.algebra.times(constant, result_with_booleans)
                # print("RESULT", result)
                volume = self.algebra.plus(volume, result)

                # exit(0)
                # continuous_vars = ContinuousVars(abstractions, var_to_lit)
                # amc(continuous_vars, support)
                # print(*["{}: {}".format(k, v) for k, v in continuous_vars.index_to_real_vars.items()], sep="\n")
                #
                # semiring_conprov = ContinuousProvenanceSemiring(abstractions, var_to_lit)
                # result = amc(semiring_conprov, support)
                # for index, variables in semiring_conprov.index_to_conprov.items():
                #     print(self.manager, variables)
                #
                # import sys
                # sys.exit()
                # semiring_inttags = IntTagSemiring(abstractions, var_to_lit, semiring_conprov.index_to_conprov)
                # _ = amc(semiring_inttags, support)
                # int_tags = semiring_inttags.int_tags
                # int_tags = {}
                # # TODO fill int tags correctly
                # convex_supports = amc(WMISemiringPint(abstractions, var_to_lit, int_tags), support)
                # for convex_support, variables in convex_supports:
                #     missing_variable_count = len(self.domain.bool_vars) - len(variables)
                #     vol = self.integrate_convex(convex_support, world_weight.to_smt()) * 2 ** missing_variable_count
                #     volume += vol

            for support in terms_dict.values():
                support.deref()
        else:
            for w_weight, world_support in piecewise_function.sdd_dict.items():
                support = support_sdd & world_support
                convex_supports = amc(WMISemiring(abstractions, var_to_lit), support)
                print("#convex regions", len(convex_supports))
                start = time.time()
                for convex_support, variables in convex_supports:
                    missing_variable_count = len(self.domain.bool_vars) - len(variables)
                    vol = self.integrate_convex(convex_support, w_weight.to_smt()) * 2 ** missing_variable_count
                    volume = self.algebra.plus(volume, self.algebra.real(vol))
                print(time.time() - start)
        return self.algebra.to_float(volume)

    def copy(self, domain, support, weight):
        return NativeXsddEngine(self.domain, support, weight, self.backend, self.factorized, self.manager, self.algebra,
                                self.find_conflicts, self.ordered)

    def __str__(self):
        solver_string = "n-xsdd:b{}".format(self.backend)
        if self.factorized:
            solver_string += ":factorized"
        if self.find_conflicts:
            solver_string += ":prune"
        if self.ordered:
            solver_string += ":order"
        return solver_string



