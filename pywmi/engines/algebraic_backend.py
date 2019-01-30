import pysmt.shortcuts as smt
from pysmt.typing import REAL
import sympy
try:
    import psipy
except ImportError:
    psipy = None


class AlgebraBackend(object):
    @classmethod
    def zero(cls):
        return cls.real(0)

    @classmethod
    def one(cls):
        return cls.real(1)

    @classmethod
    def times(cls, a, b):
        if a == cls.zero() or b == cls.zero():
            return cls.zero()
        elif a == cls.one():
            return b
        elif b == cls.one():
            return a
        else:
            return a * b

    @classmethod
    def plus(cls, a, b):
        if a == cls.zero():
            return b
        elif b == cls.zero():
            return a
        else:
            return a + b

    @classmethod
    def symbol(cls, name):
        raise NotImplementedError()

    @classmethod
    def real(cls, float_constant):
        raise NotImplementedError()

    @classmethod
    def negate(cls, a):
        return cls.times(a, cls.real(-1))

    @classmethod
    def power(cls, a, power):
        if not isinstance(power, int) and int(power) != power:
            raise ValueError("Expected integer power, got {power}".format(power=power))
        if power < 0:
            raise ValueError("Unexpected negative power {power}".format(power=power))
        result = cls.one()
        for i in range(int(power)):
            result = cls.times(result, a)
        return result


class PySmtAlgebra(AlgebraBackend):
    @classmethod
    def symbol(cls, name):
        return smt.Symbol(name, REAL)

    @classmethod
    def real(cls, float_constant):
        return smt.Real(float_constant)

    @classmethod
    def power(cls, a, power):
        return smt.Pow(a, smt.Real(power))


class SympyAlgebra(AlgebraBackend):
    @classmethod
    def times(cls, a, b):
        return a * b

    @classmethod
    def plus(cls, a, b):
        return a + b

    @classmethod
    def negate(cls, a):
        return -a

    @classmethod
    def symbol(cls, name):
        return sympy.S(name)

    @classmethod
    def real(cls, float_constant):
        return float_constant


class PSIAlgebra(AlgebraBackend):
    @classmethod
    def times(cls, a, b):
        return psipy.mul(a,b)

    @classmethod
    def plus(cls, a, b):
        return psipy.add(a,b)

    @classmethod
    def negate(cls, a):
        return psipy.mul(psipy.S("-1"), a)

    @classmethod
    def symbol(cls, name):
        assert isinstance(name, str)
        return psipy.S(name)

    @classmethod
    def real(cls, float_constant):
        assert isinstance(float_constant, (float,int))
        return psipy.S(str(float_constant))

    @classmethod
    def power(cls, a, power):
        if not isinstance(power, int) and int(power) != power:
            raise ValueError("Expected integer power, got {power}".format(power=power))
        if power < 0:
            raise ValueError("Unexpected negative power {power}".format(power=power))
        result = psipy.pow(str(a), str(power))
        return result
