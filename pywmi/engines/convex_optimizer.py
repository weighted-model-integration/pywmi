from typing import List, Callable

from pywmi import Domain
from pywmi.smt_math import LinearInequality, Polynomial


class ConvexOptimizationBackend(object):
    def __init__(self, exact=True):
        self.exact = exact

    def optimize(self, domain: Domain, convex_bounds: List[LinearInequality], polynomial: Polynomial):
        raise NotImplementedError()

    def get_opt_bounds(self, domain: Domain, convex_bounds: List[LinearInequality]) -> (List, List):
        raise NotImplementedError()
    
    def get_opt_function(self, polynomial: Polynomial) -> Callable:
        raise NotImplementedError()