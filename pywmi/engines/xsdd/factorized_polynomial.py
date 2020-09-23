import sympy

from pywmi.smt_math import PolynomialAlgebra, CONST_KEY


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
        print(self)
        raise NotImplementedError

    @property
    def variables(self):
        return frozenset([str(v) for v in self.expression.free_symbols])

    def get_factors(self):
        constant, factors = sympy.factor_list(self.expression)
        factors = [b ** e for (b, e) in factors]
        factors = [FactorizedPolynomial(f) for f in factors]
        if not constant == 1:
            factors = [FactorizedPolynomial.from_constant(constant)] + factors
        return factors

    def __str__(self):
        return str(self.expression)

    def __repr__(self):
        return str(self)