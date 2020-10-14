from typing import List

import pysmt.shortcuts as smt

from pywmi import Domain
from pywmi.smt_math import LinearInequality, Polynomial


class ConvexIntegrationBackend(object):
    def __init__(self, exact=True):
        self.exact = exact

    def integrate(self, domain: Domain, convex_bounds: List[LinearInequality], polynomial: Polynomial):
        raise NotImplementedError()


class EngineConvexIntegrationBackend(ConvexIntegrationBackend):
    def __init__(self, engine):
        super().__init__(engine.exact)
        self.engine = engine

    def integrate(self, domain: Domain, convex_bounds: List[LinearInequality], polynomial: Polynomial):
        formula = smt.And(*[i.to_smt() for i in convex_bounds])
        return self.engine.copy(domain, formula, polynomial.to_smt()).compute_volume()
