import pysmt.shortcuts as smt
from pysmt.typing import REAL
import sympy

from pywmi.errors import InstallError
from pywmi import Domain

try:
    import psipy
except ImportError:
    psipy = None


class AlgebraBackend:
    def zero(self):
        return self.real(0)

    def one(self):
        return self.real(1)

    def times(self, a, b):
        if a == self.zero() or b == self.zero():
            return self.zero()
        elif a == self.one():
            return b
        elif b == self.one():
            return a
        else:
            return a * b

    def plus(self, a, b):
        if a == self.zero():
            return b
        elif b == self.zero():
            return a
        else:
            return a + b

    def symbol(self, name):
        raise NotImplementedError()

    def real(self, float_constant):
        raise NotImplementedError()

    def negate(self, a):
        return self.times(a, self.real(-1))

    def power(self, a, power):
        if not isinstance(power, int) and int(power) != power:
            raise ValueError("Expected integer power, got {power}".format(power=power))
        if power < 0:
            raise ValueError("Unexpected negative power {power}".format(power=power))
        result = self.one()
        for i in range(int(power)):
            result = self.times(result, a)
        return result

    def less_than(self, a, b):
        return a < b

    def less_than_equal(self, a, b):
        return a <= b

    def greater_than(self, a, b):
        return self.less_than(self.negate(a), self.negate(b))

    def greater_than_equal(self, a, b):
        return self.less_than_equal(self.negate(a), self.negate(b))


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


class PSIAlgebra(AlgebraBackend):
    def __init__(self):
        if psipy is None:
            raise InstallError("PSIAlgebra requires the psipy library to be installed")

    def times(self, a, b):
        return psipy.mul(a,b)

    def plus(self, a, b):
        return psipy.add(a,b)

    def negate(self, a):
        return psipy.mul(psipy.S("-1"), a)

    def symbol(self, name):
        assert isinstance(name, str)
        return psipy.S(name)

    def real(self, float_constant):
        assert isinstance(float_constant, (float,int))
        return psipy.S(str(float_constant))

    def power(self, a, power):
        if not isinstance(power, int) and int(power) != power:
            raise ValueError("Expected integer power, got {power}".format(power=power))
        if power < 0:
            raise ValueError("Unexpected negative power {power}".format(power=power))
        result = psipy.pow(str(a), str(power))
        return result


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
        return "(int {} (list {})]".format(expression, " ".join(variables))
