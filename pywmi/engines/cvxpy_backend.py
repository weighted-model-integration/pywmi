import logging

from typing import List

from pywmi.smt_math import LinearInequality, Polynomial, PolynomialAlgebra
from pywmi.engines.algebraic_backend import SympyAlgebra
from .convex_optimizer import ConvexOptimizationBackend
import pysmt.shortcuts as smt

logger = logging.getLogger(__name__)


class cvxpyOptimizer(ConvexOptimizationBackend):
    def __init__(self):
        super().__init__(True)

    @staticmethod
    def key_to_exponents(domain, key: tuple):
        return [key.count(v) for v in domain.real_vars]

    def optimize(self, domain, convex_bounds: List[LinearInequality], polynomial: Polynomial):
        print("Cvx bound:", [bound.to_expression(SympyAlgebra()) for bound in convex_bounds])
        print("Domain bounds:", domain.get_ul_bounds())
        print("Function:", polynomial.to_expression(PolynomialAlgebra()))
        return 1

    def __str__(self):
        return "cvxpy_opt"
