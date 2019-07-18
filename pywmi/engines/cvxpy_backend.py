import logging
from scipy.optimize import minimize, LinearConstraint, Bounds, linprog
import numpy as np

from typing import List, Callable

from pywmi import Domain
from pywmi.smt_math import LinearInequality, Polynomial
from .convex_optimizer import ConvexOptimizationBackend
# from .algebraic_backend import SympyAlgebra
# import pysmt.shortcuts as smt

logger = logging.getLogger(__name__)


class cvxpyOptimizer(ConvexOptimizationBackend):
    def __init__(self):
        super().__init__(True)

    @staticmethod
    def key_to_exponents(domain, key: tuple):
        return [key.count(v) for v in domain.real_vars]
    
    def get_opt_bounds(self, domain: Domain, convex_bounds: List[LinearInequality]) -> (List, List):
        a = [[bound.a(var) for var in domain.real_vars] for bound in convex_bounds]
        b = [bound.b() for bound in convex_bounds]
        return a, b

    def get_opt_function(self, domain: Domain, polynomial: Polynomial) -> Callable:
        return polynomial.compute_value_from_variables(domain.real_vars)
        
    def optimize(self, domain, convex_bounds: List[LinearInequality],
                 polynomial: Polynomial, min=True) -> float:
        sign = 1.0 if min else -1.0
        # print([bound.to_expression(SympyAlgebra()) for bound in convex_bounds])
        print(polynomial)
        lower_bounds, upper_bounds = domain.get_ul_bounds(polynomial.variables)
        bounds_arr = list(zip(lower_bounds, upper_bounds))
        a, b = self.get_opt_bounds(domain, convex_bounds)

        point_in_region = linprog(np.zeros(len(domain.real_vars)), np.array(a), np.array(b),
                                  bounds=np.array(bounds_arr), method="simplex")
        if point_in_region.success:
            initial_value = point_in_region.x
        else:
            return 50000     # should be last min or something like that

        bounds = Bounds(lower_bounds, upper_bounds)
        lin_constraints = LinearConstraint(a, np.full(len(b), -np.inf), b)
        return minimize(self.get_opt_function(domain, polynomial), initial_value,
                        args=(sign,), method='trust-constr', bounds=bounds,
                        constraints=lin_constraints).fun

    def __str__(self):
        return "scipy_opt"
