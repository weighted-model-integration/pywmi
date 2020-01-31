from pywmi.smt_math import PolynomialAlgebra, Polynomial, CONST_KEY
import sympy
from pywmi.sympy_utils import sympy2pysmt


class FactorizedPolynomialAlgebra(PolynomialAlgebra):
    def symbol(self, name):
        return FactorizedPolynomial(name)

    def real(self, float_constant):
        return FactorizedPolynomial.from_constant(float_constant)

    def to_float(self, real_value):
        raise NotImplementedError()


class FactorizedPolynomial:
    def __init__(self, polynomial):
        self.expression = sympy.sympify(polynomial)

    @staticmethod
    def from_constant(constant):
        return FactorizedPolynomial(constant)

    def __mul__(a, b):
        return FactorizedPolynomial(a.expression * b.expression)

    def __add__(a, b):
        return FactorizedPolynomial(a.expression + b.expression)

    def get_terms(self):
        if self.expression.is_Add:
            return [FactorizedPolynomial(r) for r in self.expression.args]
        else:
            return [self]

    def to_expression(self, algebra):
        expression = Polynomial.from_smt(sympy2pysmt(self.expression))
        expression = Polynomial.to_expression(expression, algebra)
        return expression
        # print(algebra)
        # print(self.expression)

    def to_smt(self):
        return sympy2pysmt(self.expression)

    @property
    def variables(self):
        return frozenset([str(v) for v in self.expression.free_symbols])

    def get_factors(self):
        constant, factors = sympy.factor_list(self.expression)
        factors = [b ** e for (b, e) in factors]
        factors = [Polynomial.from_smt(sympy2pysmt(f)) for f in factors]
        if not constant == 1:
            factors = [Polynomial.from_constant(constant)] + factors
        return factors
