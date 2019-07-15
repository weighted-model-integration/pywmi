import logging

from typing import List

from pywmi.smt_math import LinearInequality, Polynomial
from .convex_optimizer import ConvexOptimizationBackend
import pysmt.shortcuts as smt

logger = logging.getLogger(__name__)


class cvxpyOptimizer(ConvexOptimizationBackend):
    #pattern = re.compile(r".*Answer:\s+(-?\d+)/(\d+).*")

    def __init__(self):
        super().__init__(True)

    @staticmethod
    def key_to_exponents(domain, key: tuple):
        return [key.count(v) for v in domain.real_vars]

    def optimize(self, domain, convex_bounds: List[LinearInequality], polynomial: Polynomial):
        return 1

    def __str__(self):
        return "cvxpy_opt"
