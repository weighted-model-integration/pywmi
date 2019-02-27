from __future__ import print_function

import warnings
from typing import Type, Dict, Any, Union, Optional

import graphviz
from pysmt.fnode import FNode
from pysmt.shortcuts import Real

from pywmi.engines.algebraic_backend import AlgebraBackend, IntegrationBackend
from .decision import Decision
from .operation import Operation, Summation, Multiplication, LogicalOr, LogicalAnd


def check_node_id(node_id, name="Node id"):
    if not isinstance(node_id, int):
        raise RuntimeError("{} must be integer, was {} of type {}".format(name, node_id, type(node_id)))
    return node_id


Assignment = Dict[str, Any]
Algebra = Union[AlgebraBackend, IntegrationBackend]  # Actually Intersection
Expression = Any


class Node:
    def __init__(self, pool: 'Pool', node_id):
        self.pool = pool
        self._node_id = node_id

    @property
    def node_id(self):
        return self._node_id

    def is_terminal(self):
        raise NotImplementedError()


class TerminalNode(Node):
    def __init__(self, pool: 'Pool', node_id, expression: Expression):
        Node.__init__(self, pool, node_id)
        assert not isinstance(expression, FNode)
        self.expression = expression
        # self._symbols = tuple(map(str, expression.get_free_variables()))
        self._f = None

    @property
    def polynomial(self):
        raise NotImplementedError()

    def _get_f(self):
        raise NotImplementedError()
        # if self._f is None:
        #     self._f = sympy.lambdify(self._symbols, self._expression)
        # return self._f

    def evaluate(self, assignment: Assignment):
        # try:
        #     return self._get_f()(*[assignment[str(v)] for v in self._symbols])
        # except KeyError as e:
        #     raise RuntimeError(("The assignment {a} contains no value for variable {v} [node {n} ]"
        #           .format(a=assignment, v=e.args[0], n=self)))
        # except TypeError as e:
        #     print("Something went wrong with the evaluation of expression {e} ({s}) for assignment {a}"
        #           .format(e=self.expression, a=assignment, s=self._symbols))
        #     raise
        raise NotImplementedError()

    def __repr__(self):
        return "T(id: {}, expression: {})".format(self.node_id, self.expression)

    def is_terminal(self):
        return True


class InternalNode(Node):
    def __init__(self, pool: 'Pool', node_id, decision: Decision, child_true, child_false, native_decision=None):
        Node.__init__(self, pool, node_id)
        self.decision = decision
        self._native_decision = native_decision
        check_node_id(child_true, "Child (true)")
        self._child_true = child_true
        check_node_id(child_false, "Child (false)")
        self._child_false = child_false

    @property
    def native_decision(self):
        if self._native_decision is None:
            self._native_decision = self.decision.inequality.to_expression(self.pool.algebra)
        return self._native_decision

    @property
    def child_true(self):
        return self._child_true

    @property
    def child_false(self):
        return self._child_false

    def __repr__(self):
        return "I(id: {}, decision: {}, true: {}, false: {})"\
            .format(self.node_id, self.decision, self.child_true, self.child_false)

    def is_terminal(self):
        return False


class DefaultCache(object):
    def __init__(self, calculator):
        """
        :param callable calculator:
        """
        self._cache = dict()
        self._calculator = calculator
        self.hits = 0
        self.misses = 0

    def get(self, pool, key):
        """
        :param Pool pool: The pool this cache is used for
        :param key: The key to compute a value for
        :return: The value
        """
        if key in self._cache:
            self.hits += 1
            return self._cache[key]
        else:
            self.misses += 1
            value = self._calculator(pool, key)
            self._cache[key] = value
            return value

    def contains(self, key):
        """
        :param key: The key to lookup
        :return: True if there is a value cached for the given key, False otherwise
        """
        return key in self._cache

    def clear(self):
        """
        Clears the cache
        """
        self._cache = dict()
        self.hits = 0
        self.misses = 0


class Ordering(object):
    def test_smaller_eq(self, test_id1, test1, test_id2, test2):
        raise NotImplementedError()


class Pool:
    def __init__(self, empty=False, ordering=None, algebra: Optional[Algebra] = None):
        self._counter = 1
        self._nodes = dict()
        self._internal_map = dict()
        self._expressions = dict()
        self._tests = dict()
        self.caches = dict()
        self._apply_cache = dict()
        self._ordering = ordering
        self.algebra = algebra
        if not empty:
            self.zero_id = self.terminal(self.algebra.zero())
            self.one_id = self.terminal(self.algebra.one())
            self.pos_inf_id = 1.1  # TODO How to deal with INF
            self.neg_inf_id = 1.2

        self.add_cache("diagram", DefaultCache(lambda pool, node_id: Diagram(pool, pool.get_node(node_id))))

    def has_cache(self, name):
        return name in self.caches

    def add_cache(self, name, cache):
        if name in self.caches:
            raise RuntimeError("There is already a cache with name {}".format(name))
        self.caches[name] = cache

    def get_cached(self, name, key):
        return self.caches[name].get(self, key)

    def is_cached(self, name, key):
        return self.caches[name].contains(key)

    def change_order(self, new_ordering):
        warnings.warn("Using experimental feature: change order.", Warning)
        for cache in self.caches.values():
            cache.clear()
        self._ordering = new_ordering

    def _get_test_id(self, test):
        return self._tests.get(test, None)

    def _add_test(self, test):
        if test not in self._tests:
            self._tests[test] = len(self._tests)
        return self._tests[test]

    def get_node(self, node_id) -> Union[TerminalNode, InternalNode]:
        """
        Returns the node object associated with the given node_id
        :param int node_id: The node id
        :return: Node The node object
        """
        check_node_id(node_id)
        if node_id in self._nodes:
            return self._nodes.get(node_id)
        else:
            raise RuntimeError("No node in pool with id {}.".format(node_id))

    def terminal(self, expression: FNode):
        if expression in self._expressions:
            return self._expressions[expression]

        node_id = self._register(lambda n_id: TerminalNode(self, n_id, expression))
        self._expressions[expression] = node_id
        return node_id

    def internal(self, decision: Decision, child_true: int, child_false: int) -> int:
        assert isinstance(decision, Decision)
        check_node_id(child_true, "Child (true)")
        check_node_id(child_false, "Child (false)")

        # Collapse ite if both children are the same
        if child_true == child_false:
            return child_true

        # Collapse ite if the test is a tautology
        if len(decision.get_valid_branches()) == 1:
            return child_true if decision.get_valid_branches()[0] else child_false

        decision, child_true, child_false = decision.to_canonical(child_true, child_false)
        decision_id = self._add_test(decision)
        key = (decision_id, child_true, child_false)
        node_id = self._internal_map.get(key, None)
        if node_id is None:
            node_id = self._register(lambda n_id: InternalNode(self, n_id, decision, child_true, child_false))
            self._internal_map[key] = node_id
        return node_id

    def bool_test(self, decision: Decision) -> int:
        return self.internal(decision, self.one_id, self.zero_id)

    def _register(self, constructor):
        node_id = self._counter
        self._counter += 1
        self._nodes[node_id] = constructor(node_id)
        return node_id

    def apply(self, operation: Type[Operation], root1: int, root2: int) -> int:
        key = (operation, root1, root2)
        if key in self._apply_cache:
            return self._apply_cache[key]

        node1 = self.get_node(root1)
        node2 = self.get_node(root2)

        result = operation.compute_terminal(self, node1, node2)

        if result is None:
            # Find minimal node (or only internal node)
            if isinstance(node1, InternalNode):
                if isinstance(node2, InternalNode):
                    if self.test_smaller_eq(node1.decision, node2.decision):
                        selected_test = node1.decision
                    else:
                        selected_test = node2.decision
                else:
                    selected_test = node1.decision
            else:
                selected_test = node2.decision

            if isinstance(node1, InternalNode) and node1.decision == selected_test:
                children1 = (node1.child_true, node1.child_false)
            else:
                children1 = (node1.node_id, node1.node_id)

            if isinstance(node2, InternalNode) and node2.decision == selected_test:
                children2 = (node2.child_true, node2.child_false)
            else:
                children2 = (node2.node_id, node2.node_id)

            child_true = self.apply(operation, children1[0], children2[0])
            child_false = self.apply(operation, children1[1], children2[1])

            result = self.internal(selected_test, child_true, child_false)

        self._apply_cache[key] = result
        return result

    def test_smaller_eq(self, test1, test2):
        test_id1 = self._get_test_id(test1)
        test_id2 = self._get_test_id(test2)
        if self._ordering is None:
            # v1 = len(test1.variables)
            # v2 = len(test2.variables)
            # if v1 != v2:
            #     return v1 <= v2
            # last1 = sorted(map(str, test1.variables))[-1]
            # last2 = sorted(map(str, test2.variables))[-1]
            # if last1 != last2:
            #     return last1 <= last2
            return test_id1 <= test_id2
        else:
            return self._ordering.test_smaller_eg(test_id1, test1, test_id2, test2)

    def _transform_invert(self, terminal_node, diagram):
        if terminal_node.expression == self.algebra.one():
            return diagram.pool.zero_id
        elif terminal_node.expression == self.algebra.zero():
            return diagram.pool.one_id
        else:
            raise RuntimeError("Could not invert value {}".format(terminal_node.expression))

    def invert(self, node_id: int) -> int:
        """
        Performs a logical inversion on the diagram
        :type node_id: int
        :rtype: int
        """
        node = self.get_node(node_id)
        if not node.is_terminal():
            if node.child_true == self.one_id and node.child_false == self.zero_id:
                return self.internal(node.decision, self.zero_id, self.one_id)
            elif node.child_true == self.zero_id and node.child_false == self.one_id:
                return self.internal(node.decision, self.one_id, self.zero_id)
        else:
            if node_id == self.one_id:
                return self.zero_id
            elif node_id == self.zero_id:
                return self.one_id
            else:
                raise RuntimeError("Cannot invert leaf node that is not one or zero: {}".format(node))

        # minus_one = self.terminal("-1")
        # return self.apply(Multiplication, self.apply(Summation, node_id, minus_one), minus_one)

        to_invert = self.diagram(node_id)
        from . import leaf_transform
        return leaf_transform.transform_leaves(self._transform_invert, to_invert)

    def diagram(self, node_id):
        """
        :type node_id: int
        :rtype: Diagram
        """
        return self.get_cached("diagram", node_id)

    # @staticmethod
    # def to_json(pool):
    #     """
    #     Serializes this pool object and returns a JSON string representation that contains:
    #     1) Variables
    #     2) Tests
    #     3) Expressions
    #     4) Nodes
    #     :type pool: Pool
    #     :rtype: string
    #     """
    #     representation = {
    #         "tests": [(Decision.export_test(test), test_id) for test, test_id in pool._tests.items()],
    #         "expressions": [(str(expression), exp_id) for expression, exp_id in pool._expressions.items()],
    #         "nodes": [(key, node_id) for key, node_id in pool._internal_map.items()],
    #     }
    #     import json
    #     return json.dumps(representation)

    # @staticmethod
    # def from_json(json_string):
    #     import json
    #     representation = json.loads(json_string)
    #     pool = Pool()
    #     tests = [(Test.import_test(test_string), test_id) for test_string, test_id in representation["tests"]]
    #     tests = [t[0] for t in sorted(tests, key=lambda p: p[1])]
    #
    #     nodes = representation["nodes"] + representation["expressions"]
    #     nodes = [t[0] for t in sorted(nodes, key=lambda p: p[1])]
    #
    #     for node in nodes:
    #         if isinstance(node, list):
    #             test_id, high, low = node
    #             pool.internal(tests[test_id], high, low)
    #         else:
    #             pool.terminal(node)
    #     return pool


class Diagram:
    debug = True

    def __init__(self, pool, root_node):
        self._pool = pool
        if isinstance(root_node, Node):
            self._root_node = root_node
        elif isinstance(root_node, int):
            self._root_node = pool.get_node(root_node)
        else:
            raise RuntimeError("Unexpected root node {} of type {}".format(root_node, type(root_node)))
        self._profile = None

    @property
    def root_node(self):
        """
        :rtype: Node
        """
        return self._root_node

    @property
    def root_id(self):
        """
        Returns the id of the root node of this diagram
        :rtype: int
        """
        return self.root_node.node_id

    @property
    def pool(self):
        """
        Returns the pool of this diagram
        :rtype: Pool
        """
        return self._pool

    @property
    def profile(self):
        """
        Returns the profile of this diagram, creates a profile if none exists
        :rtype: pyxadd.walk.WalkingProfile
        """
        from .walk import get_profile
        return get_profile(self)

    def node(self, node_id):
        """
        Returns the node associated with the given node_id in the pool of this diagram
        :type node_id: int
        :rtype: Node
        """
        return self._pool.get_node(node_id)

    def evaluate(self, assignment):
        assignment = {str(k): v for k, v in assignment.items()}
        node = self.root_node

        while True:
            if isinstance(node, InternalNode):
                if node.decision.evaluate(assignment):  # node.test.operator.test(node.test.expression.subs(assignment), 0):
                    node = self.node(node.child_true)
                else:
                    node = self.node(node.child_false)
            elif isinstance(node, TerminalNode):
                return node.evaluate(assignment)
            else:
                raise RuntimeError("Unexpected node type {} of node {}".format(type(node), node))

    def reduce(self, variables=None, method="fast_smt"):
        if method == "no_reduce":
            return self

        # if method == "linear":
        #     from .reduce import LinearReduction
        #     reducer = LinearReduction(self.pool)
        if method == "smt":
            from .reduce import SmtReduce
            reducer = SmtReduce(self.pool)
        elif method == "fast_smt":
            from .reduce import SmtReduce
            reducer = SmtReduce(self.pool, fast=True)
        # elif method == "simple":
        #     from .reduce import SimpleBoundReducer
        #     reducer = SimpleBoundReducer(self.pool)
        else:
            options = "'no_reduce', 'linear', 'smt', 'fast_smt' or 'simple'"
            raise RuntimeError("Unknown reduction method {} (valid options are {})".format(method, options))

        return Diagram(self.pool, reducer.reduce(self.root_node.node_id, variables))

    def show(self, pretty = False):
        from . import view
        graphviz.Source(view.to_dot(self, pretty=pretty)).render(view=True)

    def export(self, output_path, pretty=None):
        from . import view
        if not output_path[-4:] == ".dot":
            output_path += ".dot"
        view.export(self, output_path, pretty)

    def export_png(self, output_path: str, pretty=None):
        if not output_path.endswith(".dot"):
            output_path += ".dot"
        from . import view
        graphviz.Source(view.to_dot(self, pretty=pretty)).render(filename=output_path, format="png")

    def __invert__(self):
        return Diagram(self.pool, self.pool.invert(self.root_node.node_id))

    def __add__(self, other):
        if not isinstance(other, Diagram):
            raise TypeError("Cannot sum diagram with {}".format(type(other)))
        if self.pool != other.pool:
            raise RuntimeError("Can only add diagrams from the same pool")
        return Diagram(self.pool, self.pool.apply(Summation, self.root_node.node_id, other.root_node.node_id))

    def __sub__(self, other):
        if not isinstance(other, Diagram):
            raise TypeError("Cannot subtract {} from diagram".format(type(other)))
        if self.pool != other.pool:
            raise RuntimeError("Can only substract diagrams from the same pool")
        minus_one = self.pool.terminal(Real(-1))
        return self + Diagram(self.pool, self.pool.apply(Multiplication, minus_one, other.root_node.node_id))

    def __mul__(self, other):
        if not isinstance(other, Diagram):
            raise TypeError("Cannot multiply diagram with {}".format(type(other)))
        if self.pool != other.pool:
            raise RuntimeError("Can only multiply diagrams from the same pool")
        return Diagram(self.pool, self.pool.apply(Multiplication, self.root_node.node_id, other.root_node.node_id))

    def __or__(self, other):
        if not isinstance(other, Diagram):
            raise TypeError("Cannot perform or on diagram with {}".format(type(other)))
        if self.pool != other.pool:
            raise RuntimeError("Can only operate on diagrams from the same pool")
        try:
            new_root_id = self.pool.apply(LogicalOr, self.root_node.node_id, other.root_node.node_id)
            return Diagram(self.pool, new_root_id)
        except RuntimeError as e:
            if self.debug:
                print("Runtime error occured during logical OR")
                from . import view
                graphviz.Source(view.to_dot(self) + "\n" + view.to_dot(other)).render(view=True)
            raise

    def __and__(self, other):
        if not isinstance(other, Diagram):
            raise TypeError("Cannot perform and on diagram with {}".format(type(other)))
        if self.pool != other.pool:
            raise RuntimeError("Can only operate on diagrams from the same pool")
        return Diagram(self.pool, self.pool.apply(LogicalAnd, self.root_node.node_id, other.root_node.node_id))

    # T	1	0	null
    # T	2	1	null
    # E	5	(1 * y) > 0
    # I	17	5	1	2
    # E	4	(1 + (-1 * x) + (-1 * y)) > 0
    # I	19	4	1	17
    # E	3	(1 + (-1 * y)) > 0
    # I	27	3	19	2
    # E	2	((-1 * x) + (1 * y)) > 0
    # I	28	2	19	27
    # E	1	(1 * x) > 0
    # I	29	1	1	28
    # F	7	5	(#nodes and #decisions)

    # @staticmethod
    # def import_from_string(string, pool=None):
    #     # TODO implement
    #     pattern = re.compile(r"(.*) (<|<=|>|>=|=) (.*)")
    #     tests = dict()
    #     if pool is None:
    #         pool = Pool()
    #     root_id = None
    #     for line in string.split("\n"):
    #         parts = line.split("\t")
    #         if parts[0] == "T":
    #             root_id = pool.register_node(TerminalNode(int(parts[1]), sympy.sympify(parts[2])))
    #         elif parts[0] == "E":
    #             match = pattern.match(parts[2])
    #             expression = sympy.sympify(match.group(1))
    #             operator = match.group(2)
    #             tests[int(parts[1])] = LinearTest(expression, operator)
    #         elif parts[0] == "I":
    #             pool.register_node(InternalNode(int(parts[1]), tests[int(parts[2])], int(parts[3]), int(parts[4])))
