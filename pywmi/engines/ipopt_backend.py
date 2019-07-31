import logging
from scipy.optimize import minimize, LinearConstraint, Bounds, linprog
import numpy as np
import ipopt

from typing import List, Callable

from pywmi import Domain
from pywmi.smt_math import LinearInequality, Polynomial
from .convex_optimizer import ConvexOptimizationBackend
# import pysmt.shortcuts as smt

logger = logging.getLogger(__name__)


class IpoptOptimizer(ConvexOptimizationBackend):
    def __init__(self):
        super().__init__(True)
        self.algorithm = 'trust-constr'

    @staticmethod
    def get_opt_bounds(domain: Domain, convex_bounds: List[LinearInequality]) -> (List, List):
        a = [[bound.a(var) for var in sorted(domain.real_vars)] for bound in convex_bounds]
        b = [bound.b() for bound in convex_bounds]
        return a, b

    class OptProblem(object):
        def __init__(self, domain, polynomial, convex_bounds):
            self.domain = domain
            self.polynomial = polynomial
            self.convex_bounds = convex_bounds

        def objective(self, x):
            return self.polynomial.compute_value_from_variables(
                sorted(self.domain.real_vars))(x)

        def gradient(self, x):
            return self.polynomial.compute_gradient_from_variables(
                sorted(self.domain.real_vars))(x)

        def constraints(self, x):
            a = np.array([[bound.a(var) for var in sorted(self.domain.real_vars)]
                          for bound in self.convex_bounds])
            return a @ x

        def jacobian(self, x):
            return self.gradient(x)

        def hessian(self, x):
            return self.polynomial.compute_hessian_from_variables(
                sorted(self.domain.real_vars))(x)

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
            initial_value = np.array(point_inside_region.x)
        else:
            return None

        nlp = ipopt.problem(n=len(initial_value), m=len(convex_bounds),
                            problem_obj=self.OptProblem(domain, polynomial, convex_bounds),
                            lb=lower_bounds, ub=upper_bounds,
                            cl=np.full(len(b), -2.0e19), cu=b)
        nlp.addOption('mu_strategy', 'adaptive')

        res, info = nlp.solve(initial_value)
        return {'value': self.get_opt_function(domain, polynomial)(res),
                'point': res}

    def __str__(self):
        return "scipy_opt"