import logging
from scipy.optimize import minimize, LinearConstraint, Bounds, linprog
import numpy as np

from typing import List, Callable

from pywmi import Domain
from pywmi.smt_math import LinearInequality, Polynomial
from .convex_optimizer import ConvexOptimizationBackend
# import pysmt.shortcuts as smt

logger = logging.getLogger(__name__)


class ScipyOptimizer(ConvexOptimizationBackend):
    def __init__(self):
        super().__init__(True)
        self.algorithm = 'trust-constr'

    @staticmethod
    def get_opt_bounds(domain: Domain, convex_bounds: List[LinearInequality]) -> (List, List):
        a = [[bound.a(var) for var in sorted(domain.real_vars)] for bound in convex_bounds]
        b = [bound.b() for bound in convex_bounds]
        return a, b

    @staticmethod
    def get_opt_function(domain: Domain, polynomial: Polynomial) -> Callable:
        return polynomial.compute_value_from_variables(sorted(domain.real_vars))
        
    def optimize(self, domain, convex_bounds: List[LinearInequality],
                 polynomial: Polynomial, minimization: bool = True) -> dict or None:
        lower_bounds, upper_bounds = domain.get_ul_bounds()
        bounds_arr = list(zip(lower_bounds, upper_bounds))
        a, b = self.get_opt_bounds(domain, convex_bounds)

        point_inside_region = linprog(np.zeros(len(domain.real_vars)),
                                      np.array(a), np.array(b),
                                      bounds=np.array(bounds_arr), method="simplex")
        if point_inside_region.success:
            initial_value = point_inside_region.x
        else:
            return None

        bounds = Bounds(lower_bounds, upper_bounds)
        lin_constraints = LinearConstraint(a, np.full(len(b), -np.inf), b)
        sign = 1.0 if minimization else -1.0

        result = minimize(self.get_opt_function(domain, polynomial), initial_value,
                          args=(sign,), method=self.algorithm, constraints=lin_constraints,
                          options={'verbose': 1}, bounds=bounds)
        return {'value': sign*result.fun,
                'point': dict(list(zip(sorted(domain.real_vars), result.x)))}

    def __str__(self):
        return "scipy_opt"
