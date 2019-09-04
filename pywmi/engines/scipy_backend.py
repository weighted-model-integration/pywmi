import logging
from scipy.optimize import minimize, LinearConstraint, Bounds, linprog
import numpy as np
import pypoman

from typing import List, Callable

from pywmi import Domain
from pywmi.smt_math import LinearInequality, Polynomial
from .convex_optimizer import ConvexOptimizationBackend
# import pysmt.shortcuts as smt

logger = logging.getLogger(__name__)


class ScipyOptimizer(ConvexOptimizationBackend):
    def __init__(self):
        super().__init__(True)
        self.method = 'trust-constr'
        # supported methods: trust-constr, SLSQP

    @staticmethod
    def get_opt_bounds(domain: Domain, convex_bounds: List[LinearInequality]) -> (List, List):
        a = [np.array([bound.a(var) for var in sorted(domain.real_vars)]) for bound in convex_bounds]
        b = [bound.b() for bound in convex_bounds]
        return np.array(a), np.array(b)

    @staticmethod
    def get_opt_function(domain: Domain, polynomial: Polynomial, sign: float) -> Callable:
        return polynomial.compute_value_from_variables(sorted(domain.real_vars), sign)

    @staticmethod
    def compute_gradient(domain, polynomial, sign):
        return polynomial.compute_gradient_from_variables(sorted(domain.real_vars), sign)

    @staticmethod
    def compute_hessian(domain, polynomial, sign):
        return polynomial.compute_hessian_from_variables(sorted(domain.real_vars), sign=sign)

    @staticmethod
    def get_point_inside_region(domain, a, b, bounds_arr):
        return linprog(np.zeros(len(domain.real_vars)),
                       np.array(a), np.array(b),
                       bounds=np.array(bounds_arr), method="simplex")

    def optimize(self, domain, convex_bounds: List[LinearInequality],
                 polynomial: Polynomial, minimization: bool = True) -> dict or None:
        lower_bounds, upper_bounds = domain.get_ul_bounds()
        a, b = self.get_opt_bounds(domain, convex_bounds)

        bounds_arr = list(zip(lower_bounds, upper_bounds))
        point_inside_region = self.get_point_inside_region(domain, a, b, bounds_arr)
        if point_inside_region.success:
            initial_value = np.array(pypoman.polyhedron.compute_chebyshev_center(a, b))
        else:
            return None

        if self.method == 'trust-constr':
            constraints = LinearConstraint(a, np.full(len(b), -np.inf), b)
        elif self.method == 'SLSQP':
            constraints = {'type': 'ineq',
                           'fun': lambda x: np.array([b[i] - (np.dot(x, a[i]))
                                                      for i in range(len(convex_bounds))]),
                           'jac': lambda x: -np.array(a)}
        else:
            raise Exception("Unsupported method")

        bounds = Bounds(lower_bounds, upper_bounds)
        sign = 1.0 if minimization else -1.0
        result = minimize(self.get_opt_function(domain, polynomial, sign),
                          initial_value,
                          method=self.method,
                          constraints=constraints,
                          jac=self.compute_gradient(domain, polynomial, sign),
                          options={'disp': True},
                          bounds=bounds)

        return {'value': sign * result.fun,
                'point': dict(list(zip(sorted(domain.real_vars), result.x)))}

    def __str__(self):
        return "scipy_opt"
