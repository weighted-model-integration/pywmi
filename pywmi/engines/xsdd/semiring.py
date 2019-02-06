import functools
from typing import List, Tuple, Set, Any, Union, Dict
from .sdd_iterator import SddIterator

try:
    from pysdd.sdd import SddNode
except ImportError:
    SddNode = None


class SddWalker(object):
    def walk_true(self, node):
        raise NotImplementedError()

    def walk_false(self, node):
        raise NotImplementedError()

    def walk_and(self, prime_result, sub_result, prime_node, sub_node):
        raise NotImplementedError()

    def walk_or(self, child_results, node):
        raise NotImplementedError()

    def walk_literal(self, l, node):
        raise NotImplementedError()


class Semiring(object):
    def times_neutral(self):
        raise NotImplementedError()

    def plus_neutral(self):
        raise NotImplementedError()

    def times(self, a, b):
        raise NotImplementedError()

    def plus(self, a, b):
        raise NotImplementedError()

    def negate(self, a):
        raise NotImplementedError()

    def positive_weight(self, a):
        raise NotImplementedError()

    def weight(self, a):
        if a < 0:
            return self.negate(self.positive_weight(-a))
        else:
            return self.positive_weight(a)


class SemiringWalker(SddWalker):
    def __init__(self, semiring):
        self.semiring = semiring

    def walk_true(self, node_id):
        return self.semiring.times_neutral()

    def walk_false(self, node_id):
        return self.semiring.plus_neutral()

    def walk_and(self, prime_result, sub_result, prime_node, sub_node):
        return self.semiring.times(prime_result, sub_result)

    def walk_or(self, child_results, node_id):
        if len(child_results) == 0:
            return self.semiring.plus_neutral()
        elif len(child_results) == 1:
            return child_results[0]
        else:
            result = child_results[0]
            for child_result in child_results[1:]:
                result = self.semiring.plus(result, child_result)
            return result

    def walk_literal(self, l, node_id):
        return self.semiring.weight(l)


class WMCSemiring(Semiring):
    def __init__(self, weights):
        self.weights = weights

    def times_neutral(self):
        return 1.0

    def plus_neutral(self):
        return 0.0

    def times(self, a, b, index=None):
        return a * b

    def plus(self, a, b, index=None):
        return a + b

    def negate(self, a):
        return 1.0 - a

    def positive_weight(self, a):
        return self.weights[a]


def amc(semiring, sdd, smooth=False, return_cache=False):
    # type: (Semiring, SddNode, bool, bool) -> Union[Any, Tuple[Any, Dict]]
    return walk(SemiringWalker(semiring), sdd, smooth=smooth, return_cache=return_cache)


# noinspection PyUnusedLocal
def walk_callback(walker, node, rvalues, expected_prime_vars, expected_sub_vars):
    # type: (SddWalker, SddNode, List[Tuple[int, int, Set[int], Set[int]]], Set[int], Set[int]) -> Any
    if rvalues is None:
        # Leaf
        if node.is_true():
            return walker.walk_true(node)
        elif node.is_false():
            return walker.walk_false(node)
        elif node.is_literal():
            return walker.walk_literal(node.literal, node)
        else:
            raise Exception("Unknown leaf type for node {}".format(node))
    else:
        # Decision node
        if not node.is_decision():
            raise Exception("Expected a decision node for node {}".format(node))
        child_results = []
        for mc_prime, mc_sub, prime_vars, sub_vars, prime, sub in rvalues:
            # if prime_vars is not None:
            #     nb_missing_vars = len(expected_prime_vars) - len(prime_vars)
            #     prime_smooth_factor = 2 ** nb_missing_vars
            # else:
            #     prime_smooth_factor = 1
            # if sub_vars is not None:
            #     nb_missing_vars = len(expected_sub_vars) - len(sub_vars)
            #     sub_smooth_factor = 2 ** nb_missing_vars
            # else:
            #     sub_smooth_factor = 1
            child_results.append(walker.walk_and(mc_prime, mc_sub, prime, sub))
        return walker.walk_or(child_results, node)


def walk(walker, sdd, smooth=False, return_cache=False):
    # type: (SddWalker, SddNode, bool, bool) -> Union[Any, Tuple[Any, Dict]]
    it = SddIterator(sdd.manager, smooth=smooth)
    result = it.depth_first(sdd, functools.partial(walk_callback, walker))
    return (result, it._wmc_cache) if return_cache else result
