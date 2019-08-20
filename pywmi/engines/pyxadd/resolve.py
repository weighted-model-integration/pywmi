from functools import partial
from typing import Any, Optional
import logging

from pysmt.fnode import FNode
from pysmt.shortcuts import simplify, FALSE, TRUE, Real, Symbol
from pysmt.typing import BOOL, REAL

from .operation import Multiplication, Summation
from .decision import Decision
from pywmi.smt_math import Polynomial, LinearInequality
from .core import Pool, Diagram, TerminalNode, InternalNode
from . import view as exporting
from . import leaf_transform

logger = logging.getLogger(__name__)
Expression = Any


class ResolveIntegrator(object):
    FULL_REDUCE = (True, True, True)
    NO_PRODUCT_REDUCE = (True, False, True)
    NO_SUM_REDUCE = (True, True, False)
    NO_SUM_PRODUCT_REDUCE = (True, False, False)
    NO_REDUCE = (False, False, False)

    def __init__(self, pool: Pool, debug_path=None, cache_result=True, reduce_strategy=None):
        self.pool = pool
        self.debug_path = debug_path
        self.cache_hits = 0
        self.cache_calls = 0
        self.ub_cache = None
        self.lb_cache = None
        self.cache_result = cache_result
        self.resolve_cache = None
        self.symbolic_integration_enabled = False
        self.reduce_strategy = reduce_strategy or self.FULL_REDUCE
        self.method = "fast_smt" if self.reduce_strategy != self.NO_REDUCE else "no_reduce"
        if self.cache_result:
            if not self.pool.has_cache(__name__):
                self.pool.add_cache(__name__, dict())
            self.resolve_cache = self.pool.caches[__name__]

    def export(self, diagram_to_export, name):
        if self.debug_path is not None:
            if not name.endswith(".dot"):
                name += ".dot"
            exporting.export(diagram_to_export, "{}/{}".format(self.debug_path, name), print_node_ids=True)

    def symbolic_integrator(self, var: FNode, terminal_node: TerminalNode, d: Diagram):
        algebra = self.pool.algebra
        sym = algebra.symbol(var.symbol_name())
        lb = algebra.symbol("_lb")
        ub = algebra.symbol("_ub")
        expression_bounds = algebra.times(algebra.greater_than_equal(sym, lb), algebra.less_than_equal(sym, ub))
        result = algebra.integrate(None, algebra.times(expression_bounds, terminal_node.expression), sym)
        return self.pool.terminal(result)

    def concrete_integrate(self, expression: Expression, var: FNode, lb: FNode, ub: FNode, prefix) -> Expression:
        logger.debug("%s integrate %s, %s <= %s <= %s", prefix, expression, lb, var, ub)
        algebra = self.pool.algebra
        sym = algebra.symbol(var.symbol_name())
        lb = Polynomial.from_smt(lb).to_expression(algebra)
        ub = Polynomial.from_smt(ub).to_expression(algebra)
        expression_bounds = algebra.times(algebra.greater_than_equal(sym, lb), algebra.less_than_equal(sym, ub))
        result = algebra.integrate(None, algebra.times(expression_bounds, expression), [sym])
        result = algebra.get_flat_expression(result)
        logger.debug("%s \t          = %s", prefix, result)
        return result

    def integrate(self, node_id: int, var: FNode) -> int:
        self.ub_cache = dict()
        self.lb_cache = dict()

        if self.reduce_strategy[0]:
            node_id = self.pool.diagram(node_id).reduce(method=self.method).root_id

        if logger.isEnabledFor(logging.DEBUG):
            self.pool.diagram(node_id).export_png("log/integrate_{}_d_{}".format(node_id, var), pretty=True)

        if var.symbol_type() != BOOL and self.symbolic_integration_enabled:
            integrator = partial(self.symbolic_integrator, var)
            integrated = leaf_transform.transform_leaves(integrator, self.pool.diagram(node_id))
        else:
            integrated = node_id

        # self.export(self.pool.diagram(integrated), "integrated")
        result_id = self.resolve_lb_ub(integrated, var)
        # result_id = order.order(self.pool.diagram(self.resolve_lb_ub(integrated, var))).root_id

        self.ub_cache = None
        self.lb_cache = None

        if all(self.reduce_strategy):
            result_id = self.pool.diagram(result_id).reduce(method=self.method).root_id
        return result_id

    def add_to_cache(self, key, result: int) -> int:
        if self.cache_result:
            self.resolve_cache[key] = result
        return result

    def resolve_lb_ub(self, node_id: int, var: FNode, ub: Optional[FNode] = None, lb: Optional[FNode] = None,
                      prefix="") -> int:
        new_prefix = "  " + prefix
        method = self.method  # "fast_smt"
        # prefix = rl * "." + "({})({})({})".format(node_id, ub, lb)
        # print(prefix + " enter")

        logger.debug("%s resolve %s var=%s lb=%s ub=%s", prefix, node_id, var, lb, ub)

        if self.cache_result:
            key = (node_id, ub, lb)
            self.cache_calls += 1
            # print key, self.cache_calls, self.cache_hits
            if key in self.resolve_cache:
                # print("cache hit", self.cache_hits)
                self.cache_hits += 1
                # print("Cache hit for key={}".format(key))
                return self.resolve_cache[key]

            cache_result = partial(self.add_to_cache, key)
        else:
            cache_result = lambda r: r

        node = self.pool.get_node(node_id)
        # print "ub_lb_resolve node: {}, ub: {}, lb: {}, {} : {}".format(node, ub, lb, hash(str(ub)), hash(str(lb)))
        # leaf
        algebra = self.pool.algebra
        if node.is_terminal():
            if node.node_id == self.pool.zero_id:
                return self.pool.zero_id
            if var.symbol_type() == BOOL:
                return self.pool.terminal(algebra.times(algebra.real(2), node.expression))

            if ub is None or lb is None:
                # TODO: to deal with unbounded constraints, we should either return 0 if we've seen bounds
                # or f(inf) if we haven't seen bounds
                return cache_result(self.pool.zero_id)
            else:
                # ub_sub = self.operator_to_bound(ub, var)
                # lb_sub = self.operator_to_bound(lb, var)

                if self.symbolic_integration_enabled:
                    raise NotImplementedError()
                else:
                    expression = self.concrete_integrate(node.expression, var, lb, ub, prefix)

                # print "->", self.pool.get_node(res)
                return cache_result(self.pool.terminal(expression))
                # not leaf

        assert isinstance(node, InternalNode)
        if var in node.decision.variables:
            # Variable occurs in test

            if var.symbol_type() == BOOL:
                return self.pool.apply(Summation, node.child_true, node.child_false)

            var_coefficient = node.decision.inequality.coefficient(str(var))
            if var_coefficient > 0:
                # True branch is upper-bound
                ub_inequality = node.decision.inequality
                ub_branch = node.child_true
                lb_branch = node.child_false
            else:
                # False branch is upper-bound
                ub_inequality = node.decision.inequality.inverted()
                ub_branch = node.child_false
                lb_branch = node.child_true
            # ub_at_node = self.operator_to_bound(operator, var)
            # lb_at_node = self.operator_to_bound((~operator).to_canonical(), var)

            lb_inequality = ub_inequality.inverted()

            var_name = var.symbol_name()
            new_bound = self.operator_to_bound(ub_inequality, var_name)
            # lb_expr = self.operator_to_bound(lb_inequality, var_name)
            # consistency_test = simplify(lb_expr <= ub_expr)

            pass_ub = False
            if lb is not None:
                consistency_test = simplify(lb < new_bound)
                if consistency_test == FALSE():
                    # this branch is infeasible
                    ub_consistency = self.pool.zero_id
                    some_or_best_ub = self.pool.zero_id
                    pass_ub = True
                elif consistency_test == TRUE():
                    ub_consistency = self.pool.one_id
                else:
                    ub_consistency = self.pool.bool_test(Decision(consistency_test))
            else:
                ub_consistency = self.pool.one_id

            if ub is not None and not pass_ub:
                tighter_ub_test = simplify(new_bound < ub)
                if tighter_ub_test == TRUE():
                    some_ub = self.pool.zero_id
                else:
                    some_ub = self.resolve_lb_ub(ub_branch, var, ub=ub, lb=lb, prefix=new_prefix)

                if tighter_ub_test == FALSE():
                    best_ub = self.pool.zero_id
                else:
                    best_ub = self.resolve_lb_ub(ub_branch, var, ub=new_bound, lb=lb, prefix=new_prefix)

                best_ub = self.pool.diagram(best_ub).reduce(method=method).root_id  # RED
                some_ub = self.pool.diagram(some_ub).reduce(method=method).root_id  # RED

                some_or_best_ub = self.pool.internal(Decision(tighter_ub_test), best_ub, some_ub)
            elif not pass_ub:
                some_or_best_ub = self.resolve_lb_ub(ub_branch, var, ub=new_bound, lb=lb, prefix=new_prefix)

            pass_lb = False
            if ub is not None:
                consistency_test = simplify(new_bound < ub)
                if consistency_test == FALSE():
                    # this branch is infeasible
                    lb_consistency = self.pool.zero_id
                    some_or_best_lb = self.pool.zero_id
                    pass_lb = True
                    if consistency_test == TRUE():
                        lb_consistency = self.pool.one_id
                else:
                    lb_consistency = self.pool.bool_test(Decision(consistency_test))
            else:
                lb_consistency = self.pool.one_id

            if lb is not None and not pass_lb:
                tighter_lb_test = simplify(new_bound > lb)
                if tighter_lb_test == TRUE():
                    some_lb = self.pool.zero_id
                else:
                    some_lb = self.resolve_lb_ub(lb_branch, var, ub=ub, lb=lb, prefix=new_prefix)

                if tighter_lb_test == FALSE():
                    best_lb = self.pool.zero_id
                else:
                    best_lb = self.resolve_lb_ub(lb_branch, var, ub=ub, lb=new_bound, prefix=new_prefix)

                best_lb = self.pool.diagram(best_lb).reduce(method=method).root_id  # RED
                some_lb = self.pool.diagram(some_lb).reduce(method=method).root_id  # RED

                some_or_best_lb = self.pool.internal(Decision(tighter_lb_test), best_lb, some_lb)
            elif not pass_lb:
                some_or_best_lb = self.resolve_lb_ub(lb_branch, var, ub=ub, lb=new_bound, prefix=new_prefix)

            lb_branch = self.pool.apply(Multiplication, some_or_best_lb, lb_consistency)
            ub_branch = self.pool.apply(Multiplication, some_or_best_ub, ub_consistency)

            # print(prefix + " lb done")
            if self.reduce_strategy[1]:
                lb_branch = self.pool.diagram(lb_branch).reduce(method=method).root_id  # RED
                ub_branch = self.pool.diagram(ub_branch).reduce(method=method).root_id  # RED
            # self.export(res, "res{}_{}_{}".format(node_id, hash(str(ub)), hash(str(lb))))
            result = self.pool.apply(Summation, lb_branch, ub_branch)
            if self.reduce_strategy[2]:
                result = self.pool.diagram(result).reduce(method=method).root_id
            return cache_result(result)
        else:
            true_branch_id = self.resolve_lb_ub(node.child_true, var, ub=ub, lb=lb)
            false_branch_id = self.resolve_lb_ub(node.child_false, var, ub=ub, lb=lb)
            return cache_result(self.pool.internal(node.decision, true_branch_id, false_branch_id))

    def operator_to_bound(self, inequality: LinearInequality, var_name: str):
        result = Real(inequality.b())
        for other in inequality.variables:
            if other != var_name:
                result += Symbol(other, REAL) * Real(-inequality.coefficient(other))
        return simplify(result * Real(1 / inequality.coefficient(var_name)))


# if __name__ == "__main__":
#     the_pool = diagram.Pool()
#
#
#     def two_var_diagram():
#         import pdb
#         # pdb.set_trace()
#         bounds = b.test("x", ">=", 0) & b.test("x", "<=", 1)
#         bounds &= b.test("y", ">=", 1) & b.test("y", "<=", 3)
#         two = b.test("x", ">=", "y")
#         return b.ite(bounds, b.ite(two, b.terminal("x"), b.terminal("10")), b.terminal(0))
#
#
#     b = build.Builder(the_pool)
#     b.ints("x", "y", "a", "b", "c", "_ub", "_lb", "bla")
#     diagram1 = b.ite(b.test("x", "<=", "a"),
#                      b.ite(b.test("x", ">=", "b"),
#                            b.exp("_ub - _lb"), b.exp(0)),
#                      b.ite(b.test("x", "<=", "c"),
#                            b.exp("(_ub - _lb)**2"), b.exp(0))
#                      )
#     diagram2 = b.ite(b.test("x", ">=", "b"), b.exp("_ub - _lb"), b.exp(0))
#     bounds = b.test("x", ">=", 0) & b.test("x", "<=", 10)
#     # d = b.ite(bounds, b.terminal("x"), b.terminal(0))
#
#     d = two_var_diagram()
#
#     operator_1 = test.LinearTest("x", "<=", "a").operator
#     operator_2 = test.LinearTest("x", "<=", "2").operator
#     operator_3 = test.LinearTest("x", ">=", "a").operator
#     operator_4 = test.LinearTest("x", ">=", "2").operator
#
#     bound_resolve = BoundResolve(the_pool)
#     resolved_node_id = bound_resolve.resolve("x", operator_1, "leq", operator_2, "ub")
#     print(the_pool.get_node(resolved_node_id).test.operator)
#
#     resolved_node_id = bound_resolve.resolve("x", operator_1, "geq", operator_2, "ub")
#
#     print(the_pool.get_node(resolved_node_id).test.operator)
#
#     resolved_node_id = bound_resolve.resolve("x", operator_3, "leq", operator_4, "lb")
#     print(the_pool.get_node(resolved_node_id).test.operator)
#
#     resolved_node_id = bound_resolve.resolve("x", operator_3, "geq", operator_4, "lb")
#
#     print(the_pool.get_node(resolved_node_id).test.operator)
#     # dr = dag_resolve("x", operator_1, pool.bool_test(test.LinearTest(operator_2)), "geq", "ub")
#     # print("Diagram is {}ordered".format("" if order.is_ordered(pool.diagram(dr)) else "not "))
#     # view.export(pool.diagram(dr), "../../Dropbox/XADD Matrices/test.dot")
#     test_diagram = d
#     bound_resolve.export(test_diagram, "diagram")
#     # dr = dag_resolve("x", operator_1, diagram.root_id, "leq", "ub")
#     # view.export(pool.diagram(dr), "../../Dropbox/XADD Matrices/dr.dot")
#     # recurse(diagram.root_id)
#     dr = bound_resolve.integrate(test_diagram.root_id, "x")
#     bound_resolve.export(the_pool.diagram(dr), "result")
#
#     dr = reduce.LinearReduction(the_pool).reduce(dr)
#     # fm = fourier_motzkin(bounds.root_id, "ub")
#     bound_resolve.export(the_pool.diagram(dr), "result_reduced")
#
#     d_const = the_pool.diagram(dr)
#     for y in range(-20, 20):
#         s = 0
#         for x in range(-20, 20):
#             s += d.evaluate({"x": x, "y": y})
#         print(y, ":", s - d_const.evaluate({"y": y}))
#