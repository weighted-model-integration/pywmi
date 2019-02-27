from typing import TYPE_CHECKING

from .operation import Summation, Multiplication
from .walk import BottomUpWalker


class LeafWalker(BottomUpWalker):
    def __init__(self, f, diagram, profile=None):
        BottomUpWalker.__init__(self, diagram, profile)
        self._f = f

    def visit_terminal(self, terminal_node):
        return self._f(terminal_node, self.diagram)

    def visit_internal(self, internal_node, true_message, false_message):
        pool = self._diagram.pool
        test_node = pool.bool_test(internal_node.decision)
        return pool.apply(Summation,
                          pool.apply(Multiplication, test_node, true_message),
                          pool.apply(Multiplication, pool.invert(test_node), false_message))


def transform_leaves(f, diagram):
    node_id = LeafWalker(f, diagram).walk()
    return node_id


def to_binary(diagram):
    def _to_binary(terminal_node, d):
        expression = terminal_node.expression
        return d.pool.zero_id if expression == 0 else d.pool.one_id

    return transform_leaves(_to_binary, diagram)
