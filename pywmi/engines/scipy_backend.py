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

    @staticmethod
    def key_to_exponents(domain, key: tuple):
        return [key.count(v) for v in domain.real_vars]
    
    def get_opt_bounds(self, domain: Domain, convex_bounds: List[LinearInequality]) -> (List, List):
        a = [[bound.a(var) for var in sorted(domain.real_vars)] for bound in convex_bounds]
        b = [bound.b() for bound in convex_bounds]
        return a, b

    def get_opt_function(self, domain: Domain, polynomial: Polynomial) -> Callable:
        return polynomial.compute_value_from_variables(sorted(domain.real_vars))
        
    def optimize(self, domain, convex_bounds: List[LinearInequality],
                 polynomial: Polynomial, minimization=True) -> float or None:
        # print(sorted(domain.real_vars))
        # print(sorted(polynomial.variables))
        lower_bounds, upper_bounds = domain.get_ul_bounds()
        bounds_arr = list(zip(lower_bounds, upper_bounds))
        a, b = self.get_opt_bounds(domain, convex_bounds)

        point_inside_region = linprog(np.zeros(len(domain.real_vars)), np.array(a), np.array(b),
                                      bounds=np.array(bounds_arr), method="simplex")
        if point_inside_region.success:
            initial_value = point_inside_region.x
        else:
            return None

        bounds = Bounds(lower_bounds, upper_bounds)
        lin_constraints = LinearConstraint(a, np.full(len(b), -np.inf), b)
        sign = 1.0 if minimization else -1.0

        result = minimize(self.get_opt_function(domain, polynomial), initial_value,
                          args=(sign,), method='trust-constr', constraints=lin_constraints,
                          options={'verbose': 1}, bounds=bounds)
        return {'value': sign*result.fun,
                'point': dict(list(zip(sorted(domain.real_vars), result.x)))}

    def __str__(self):
        return "scipy_opt"


def objective(x):
    x0, x1, x2, x3 = x[0], x[1], x[2], x[3]
    return x0*x1*x2*x3*1.0 + x0*x1*x2*(-1.0) + x0*x1*x3*(-1.0) + x0*x1*1.0 + x0*x2*x3*(-1.0) + x0*x2*1.0 + x0*x3*1.0 + x0*(-1.0) + x1*x2*x3*(-1.0) + x1*x2*1.0 + x1*x3*1.0 + x1*(-1.0) + x2*x3*1.0 + x2*(-1.0) + x3*(-1.0) + 1.0

