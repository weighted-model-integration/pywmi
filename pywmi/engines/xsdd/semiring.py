import functools
from typing import List, Tuple, Set, Any

try:
    import pysdd.iterator as sdd_it
    from pysdd.sdd import SddNode
except ImportError:
    sdd_it = None
    SddNode = None


class Semiring(object):
    def times_neutral(self):
        raise NotImplementedError()

    def plus_neutral(self):
        raise NotImplementedError()

    def times(self, a, b, index=None):
        raise NotImplementedError()

    def plus(self, a, b, index=None):
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


def amc_callback(semiring, node, rvalues, expected_prime_vars, expected_sub_vars):
    # type: (Semiring, SddNode, List[Tuple[int, int, Set[int], Set[int]]], Set[int], Set[int]) -> Any
    if rvalues is None:
        # Leaf
        if node.is_true():
            return semiring.times_neutral()
        elif node.is_false():
            return semiring.plus_neutral()
        elif node.is_literal():
            return semiring.weight(node.literal)
        else:
            raise Exception("Unknown leaf type for node {}".format(node))
    else:
        # Decision node
        if not node.is_decision():
            raise Exception("Expected a decision node for node {}".format(node))
        rvalue = semiring.plus_neutral()
        for mc_prime, mc_sub, prime_vars, sub_vars in rvalues:
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
            rvalue = semiring.plus(rvalue, semiring.times(mc_prime, mc_sub), node.id)
        return rvalue


def amc(semiring, sdd, smooth=False):
    # type: (Semiring, SddNode, bool) -> Any
    it = sdd_it.SddIterator(sdd.manager, smooth=smooth)
    amc = it.depth_first(sdd, functools.partial(amc_callback, semiring))
    amc_cache = it._wmc_cache

    return amc, amc_cache
