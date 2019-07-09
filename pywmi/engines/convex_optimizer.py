from typing import List

from pywmi import Domain
from pywmi.smt_math import LinearInequality, Polynomial


class ConvexOptimizationBackend(object):
    def __init__(self, exact=True):
        self.exact = exact

    def optimize(self, domain: Domain, convex_bounds: List[LinearInequality], polynomial: Polynomial):
        raise NotImplementedError()
