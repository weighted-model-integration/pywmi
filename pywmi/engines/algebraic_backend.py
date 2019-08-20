from fractions import Fraction
from typing import TypeVar, Any

import pysmt.shortcuts as smt
from pysmt.fnode import FNode
from pysmt.typing import REAL
import sympy

from pywmi.errors import InstallError
from pywmi import Domain

try:
    import psipy
except ImportError:
    psipy = None


E = Any


class AlgebraBackend:
    def zero(self) -> E:
        return self.real(0)

    def one(self) -> E:
        return self.real(1)

    def times(self, a: E, b: E) -> E:
        if a == self.zero() or b == self.zero():
            return self.zero()
        elif a == self.one():
            return b
        elif b == self.one():
            return a
        else:
            return a * b

    def plus(self, a: E, b: E) -> E:
        if a == self.zero():
            return b
        elif b == self.zero():
            return a
        else:
            return a + b

    def symbol(self, name: str) -> E:
        raise NotImplementedError()

    def real(self, float_constant: float) -> E:
        raise NotImplementedError()

    def negate(self, a: E) -> E:
        return self.times(a, self.real(-1))

    def power(self, a: E, power: int) -> E:
        if not isinstance(power, int) and int(power) != power:
            raise ValueError("Expected integer power, got {power}".format(power=power))
        if power < 0:
            raise ValueError("Unexpected negative power {power}".format(power=power))
        result = self.one()
        for i in range(int(power)):
            result = self.times(result, a)
        return result

    def less_than(self, a: E, b: E) -> E:
        return a < b

    def less_than_equal(self, a: E, b: E) -> E:
        return a <= b

    def greater_than(self, a: E, b: E) -> E:
        return self.less_than(self.negate(a), self.negate(b))

    def greater_than_equal(self, a: E, b: E) -> E:
        return self.less_than_equal(self.negate(a), self.negate(b))

    def to_float(self, real_value: E) -> float:
        raise NotImplementedError()

    def get_flat_expression(self, expression_with_conditions: E) -> E:
        return expression_with_conditions

    def parse_condition(self, condition: FNode) -> E:
        from pywmi.smt_math import LinearInequality
        return LinearInequality.from_smt(condition).to_expression(self)


class IntegrationBackend:
    def __init__(self, exact=True):
        self.exact = exact

    def integrate(self, domain: Domain, expression, variables=None):
        raise NotImplementedError()


class PySmtAlgebra(AlgebraBackend):
    def symbol(self, name):
        return smt.Symbol(name, REAL)

    def real(self, float_constant):
        return smt.Real(float_constant)

    def power(self, a, power):
        return smt.Pow(a, smt.Real(power))

    def less_than(self, a, b):
        return smt.Ite(a < b, self.one, self.zero())

    def less_than_equal(self, a, b):
        return smt.Ite(a <= b, self.one, self.zero())

    def to_float(self, real_value):
        return float(real_value.constant_value)


class SympyAlgebra(AlgebraBackend):
    def times(self, a, b):
        return a * b

    def plus(self, a, b):
        return a + b

    def negate(self, a):
        return -a

    def symbol(self, name):
        return sympy.S(name)

    def real(self, float_constant):
        return float_constant

    def to_float(self, real_value):
        return float(real_value)


class PSIAlgebra(AlgebraBackend, IntegrationBackend):
    def __init__(self, integrate_poly=True):
        super().__init__()
        self.integrate_poly = integrate_poly
        if psipy is None:
            raise InstallError("PSIAlgebra requires the psipy library to be installed")

    def times(self, a, b):
        return psipy.mul(a, b)

    def plus(self, a, b):
        return psipy.add(a,b)

    def negate(self, a):
        return psipy.mul(psipy.S("-1"), a)

    def symbol(self, name):
        assert isinstance(name, str)
        return psipy.S(name)

    def real(self, float_constant):
        assert isinstance(float_constant, (float, int))
        if int(float_constant) == float_constant:
            return psipy.S("{}".format(int(float_constant)))
        # return psipy.S("{:.32f}".format(float_constant))
        fraction = Fraction(float_constant).limit_denominator()
        return psipy.S("{}/{}".format(fraction.numerator, fraction.denominator))

    def less_than(self, a, b):
        return psipy.less(a, b)

    def less_than_equal(self, a, b):
        return psipy.less_equal(a, b)

    # def power(self, a, power):
    #     if not isinstance(power, int) and int(power) != power:
    #         raise ValueError("Expected integer power, got {power}".format(power=power))
    #     if power < 0:
    #         raise ValueError("Unexpected negative power {power}".format(power=power))
    #     result = psipy.pow(str(a), str(power))
    #     return result

    def integrate(self, domain: Domain, expression, variables=None):
        if self.integrate_poly:
            result = psipy.integrate_poly(variables, expression)
        else:
            result = psipy.integrate(variables, expression)
        return result
        # return psipy.integrate(variables, expression)

    def to_float(self, real_value):
        string_value = str(psipy.simplify(real_value))
        if "/" in string_value:
            parts = string_value.split("/", 1)
            return float(parts[0]) / float(parts[1])
        return float(string_value)

    def get_flat_expression(self, expression_with_conditions):
        result = psipy.filter_iverson(expression_with_conditions)
        return psipy.simplify(result)


class StringAlgebra(AlgebraBackend, IntegrationBackend):
    def __init__(self):
        AlgebraBackend.__init__(self)
        IntegrationBackend.__init__(self, True)

    def times(self, a, b):
        if a == self.one():
            return b
        elif b == self.one():
            return a
        if a == self.zero() or b == self.zero():
            return self.zero()
        return "{} * {}".format(a, b)

    def plus(self, a, b):
        if a == self.zero():
            return b
        elif b == self.zero():
            return a
        return "({} + {})".format(a, b)

    def negate(self, a):
        return "-{}".format(a)

    def symbol(self, name):
        return name

    def real(self, float_constant):
        return str(float_constant)

    def less_than(self, a, b):
        return "[{} < {}]".format(a, b)

    def less_than_equal(self, a, b):
        return "[{} <= {}]".format(a, b)

    def integrate(self, domain: Domain, expression, variables=None):
        variables = variables or domain.real_vars
        return "I[{}, d({})]".format(expression, " ".join(variables))

    def to_float(self, real_value):
        return float(real_value)

    def power(self, a, power):
        if not isinstance(power, int) and int(power) != power:
            raise ValueError("Expected integer power, got {power}".format(power=power))
        if power < 0:
            raise ValueError("Unexpected negative power {power}".format(power=power))
        result = psipy.pow(str(a), str(power))
        return result


class XaddAlgebra(AlgebraBackend, IntegrationBackend):
    def __init__(self):
        AlgebraBackend.__init__(self)
        IntegrationBackend.__init__(self, True)

    def times(self, a, b):
        if a == self.one():
            return b
        elif b == self.one():
            return a
        if a == self.zero() or b == self.zero():
            return self.zero()
        return "(* {} {})".format(a, b)

    def plus(self, a, b):
        if a == self.zero():
            return b
        elif b == self.zero():
            return a
        return "(+ {} {})".format(a, b)

    def negate(self, a):
        return "(- (const real 0) {})".format(a)

    def symbol(self, name):
        return "(var real {})".format(name)

    def real(self, float_constant):
        return "(const real {})".format(float_constant)

    def less_than(self, a, b):
        return "(ite (< {} {}) (const real 1) (const real 0))".format(a, b)

    def less_than_equal(self, a, b):
        return "(ite (<= {} {}) (const real 1) (const real 0))".format(a, b)

    def integrate(self, domain: Domain, expression, variables=None):
        variables = variables or domain.real_vars
        return "(int {} (list {}))".format(expression, " ".join(variables))

    def to_float(self, real_value):
        raise NotImplementedError()
