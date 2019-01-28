from typing import List

from pywmi import Domain
from pywmi.smt_math import LinearInequality, Polynomial


class IntegrationBackend(object):
    def __init__(self, exact=True):
        self.exact = exact

    def partially_integrate(self, domain: Domain, convex_bounds: List[LinearInequality], polynomial: Polynomial,
                            variables: List[str]):
        raise NotImplementedError()

    def integrate(self, domain: Domain, convex_bounds: List[LinearInequality], polynomial: Polynomial):
        raise NotImplementedError()
