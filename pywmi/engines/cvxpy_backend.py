import logging
from scipy.optimize import minimize, LinearConstraint, Bounds
import numpy as np

from typing import List, Callable

from pywmi import Domain
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
    
    def get_opt_bounds(self, domain: Domain, convex_bounds: List[LinearInequality]) -> (List, List):
        A = [[bound.a(var) for var in domain.real_vars] for bound in convex_bounds]
        b =  [bound.b() for bound in convex_bounds]
        return A, b

    def get_opt_function(self, domain: Domain, polynomial: Polynomial) -> Callable:
        return polynomial.compute_value_from_variables(domain.real_vars)
        
    def optimize(self, domain, convex_bounds: List[LinearInequality], polynomial: Polynomial):
        initial_value = np.zeros(len(domain.real_vars),)
        lower_bounds, upper_bounds = domain.get_ul_bounds()
        bounds = Bounds(lower_bounds, upper_bounds)
        A, b = self.get_opt_bounds(domain, convex_bounds)
        constraints = LinearConstraint(A, np.full((len(b), ), -np.inf), b)
        return minimize(self.get_opt_function(domain, polynomial), initial_value, 
                        method='trust-constr',
                        bounds=bounds, constraints=constraints)
                        
    def __str__(self):
        return "cvxpy_opt"
