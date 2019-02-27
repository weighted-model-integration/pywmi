class Operation(object):
    def __init__(self, symbol):
        self._symbol = symbol

    @property
    def symbol(self):
        return self._symbol

    @classmethod
    def compute_terminal(cls, pool, node1, node2):
        # deal with NaN?
        # special cases
        # two terminals
        raise NotImplementedError()

    def __hash__(self):
        return hash(self.symbol)


class Multiplication(Operation):
    def __init__(self):
        Operation.__init__(self, "*")

    @classmethod
    def compute_terminal(cls, pool, node1, node2):
        # TODO deal with NaN?
        if node1.node_id == pool.zero_id or node2.node_id == pool.zero_id:
            return pool.zero_id
        elif node1.node_id == pool.one_id:
            return node2.node_id
        elif node2.node_id == pool.one_id:
            return node1.node_id
        elif node1.is_terminal() and node2.is_terminal():
            algebra = pool.algebra
            return pool.terminal(algebra.get_flat_expression(algebra.times(node1.expression, node2.expression)))
        return None


class Summation(Operation):
    def __init__(self):
        Operation.__init__(self, "+")

    @classmethod
    def compute_terminal(cls, pool, node1, node2):
        # TODO deal with NaN?
        if node1.node_id == pool.zero_id:
            return node2.node_id
        elif node2.node_id == pool.zero_id:
            return node1.node_id
        elif node1.node_id == pool.pos_inf_id or node1.node_id == pool.neg_inf_id:
            return node1.node_id
        elif node2.node_id == pool.pos_inf_id or node2.node_id == pool.neg_inf_id:
            return node2.node_id
        elif node1.is_terminal() and node2.is_terminal():
            algebra = pool.algebra
            return pool.terminal(algebra.get_flat_expression(algebra.plus(node1.expression, node2.expression)))
        return None


# TODO Review logical operations, is terminal correct? Seems to be missing edge cases
class LogicalOr(Operation):
    def __init__(self):
        Operation.__init__(self, "|")

    @classmethod
    def compute_terminal(cls, pool, node1, node2):
        # TODO deal with NaN?
        if node1.is_terminal() and node2.is_terminal() \
                and ((node1.node_id != pool.zero_id and node1.node_id != pool.one_id)
                     or (node2.node_id != pool.zero_id and node2.node_id != pool.one_id)):
            raise RuntimeError("Nodes must be one or zero")

        if node1.node_id == pool.zero_id:
            return node2.node_id
        elif node1.node_id == pool.one_id:
            return pool.one_id
        elif node2.node_id == pool.zero_id:
            return node1.node_id
        elif node2.node_id == pool.one_id:
            return pool.one_id
        elif node1.is_terminal() and node2.is_terminal():
            raise RuntimeError("Cases should be covered")
        return None


class LogicalAnd(Operation):
    def __init__(self):
        Operation.__init__(self, "&")

    @classmethod
    def compute_terminal(cls, pool, node1, node2):
        # TODO deal with NaN?
        if node1.is_terminal() and node2.is_terminal() \
                and ((node1.node_id != pool.zero_id and node1.node_id != pool.one_id)
                     or (node2.node_id != pool.zero_id and node2.node_id != pool.one_id)):
            raise RuntimeError("Nodes must be one or zero, were {} and {}".format(node1, node2))

        if node1.node_id == pool.one_id:
            return node2.node_id
        elif node1.node_id == pool.zero_id:
            return pool.zero_id
        elif node2.node_id == pool.one_id:
            return node1.node_id
        elif node2.node_id == pool.zero_id:
            return pool.zero_id
        elif node1.is_terminal() and node2.is_terminal():
            raise RuntimeError("Cases should be covered")
        return None
