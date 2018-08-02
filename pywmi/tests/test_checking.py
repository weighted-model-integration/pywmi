import numpy as np
from pysmt.shortcuts import Real, Ite, Bool, Equals, Pow

from engines.rejection import RejectionEngine
from pywmi import Domain
from pywmi import test as check
from pywmi.engines.rejection import sample


def test_simple():
    domain = Domain.make(["a", "b"], {"x": (0, 100), "y": (0, 50)})
    a, b, x, y = (domain.get_symbol(n) for n in "abxy")
    support = (a & (20 <= x) & (y <= 30) & (x <= 2 * y)) | ((0 <= x) & (y <= 40) & (x <= 2 * y))
    engine = RejectionEngine(domain, support, Real(1.0), 10)
    engine.get_samples(100)


class TestCheckingBatch(object):
    domain = Domain.make(["a", "b"], {"x": (0, 100), "y": (0, 50)})
    a = domain.get_symbol("a")
    b = domain.get_symbol("b")
    x = domain.get_symbol("x")
    y = domain.get_symbol("y")
    values = np.array([
            [1, 1, 10, 20],
            [1, 0, 20, 10],
            [0, 0, 10, 29],
            [1, 0, 99, 1],
            [0, 0, 49, 49],
        ])

    def check(self, formula):
        return list(check(self.domain, formula, self.values))

    def test_ite(self):
        assert self.check(Ite(self.a, self.x < 50, self.y < 30)) == [True, True, True, False, False]

    def test_not(self):
        assert self.check(~self.a) == [False, False, True, False, True]

    def test_or(self):
        assert self.check(self.b | (self.x > 30)) == [True, False, False, True, True]

    def test_and(self):
        assert self.check(self.a & (self.x < 30)) == [True, True, False, False, False]

    def test_lt(self):
        assert self.check(self.x < 49) == [True, True, True, False, False]

    def test_lte(self):
        assert self.check(self.x <= 49) == [True, True, True, False, True]

    def test_equals(self):
        assert self.check(Equals(self.x, Real(49))) == [False, False, False, False, True]

    def test_var_plus_var(self):
        assert self.check(self.x + self.y) == [self.values[i, 2] + self.values[i, 3] for i in range(5)]

    def test_var_plus_constant(self):
        assert self.check(self.x + 2) == [self.values[i, 2] + 2 for i in range(5)]

    def test_constant_plus_var(self):
        assert self.check(Real(3) + self.x) == [3 + self.values[i, 2] for i in range(5)]

    def test_constant_plus_constant(self):
        assert self.check(Real(3) + Real(6)) == [9 for _ in range(5)]

    def test_var_minus_var(self):
        assert self.check(self.x - self.y) == [self.values[i, 2] - self.values[i, 3] for i in range(5)]

    def test_var_minus_constant(self):
        assert self.check(self.x - Real(2)) == [self.values[i, 2] - 2 for i in range(5)]

    def test_constant_minus_var(self):
        assert self.check(Real(3) - self.x) == [3 - self.values[i, 2] for i in range(5)]

    def test_constant_minus_constant(self):
        assert self.check(Real(3) - Real(6)) == [-3 for _ in range(5)]

    def test_var_times_var(self):
        assert self.check(self.x * self.y) == [self.values[i, 2] * self.values[i, 3] for i in range(5)]

    def test_var_times_constant(self):
        assert self.check(self.x * Real(2)) == [self.values[i, 2] * 2 for i in range(5)]

    def test_constant_times_var(self):
        assert self.check(Real(3) * self.x) == [3 * self.values[i, 2] for i in range(5)]

    def test_constant_times_constant(self):
        assert self.check(Real(3) * Real(6)) == [18 for _ in range(5)]

    def test_var_pow_constant(self):
        assert self.check(Pow(self.x, Real(2))) == [self.values[i, 2] ** 2 for i in range(5)]

    def test_constant_pow_constant(self):
        assert self.check(Pow(Real(3), Real(6))) == [3**6 for _ in range(5)]

    def test_symbol(self):
        assert self.check(self.a) == [bool(self.values[i, 0]) for i in range(5)]
        assert self.check(self.b) == [bool(self.values[i, 1]) for i in range(5)]
        assert self.check(self.x) == [float(self.values[i, 2]) for i in range(5)]
        assert self.check(self.y) == [float(self.values[i, 3]) for i in range(5)]

    def test_constant(self):
        assert self.check(Bool(True)) == [True for _ in range(5)]
        assert self.check(Real(5)) == [float(5) for _ in range(5)]


class TestCheckingSingle(object):
    domain = Domain.make(["a", "b"], {"x": (0, 100), "y": (0, 50)})
    a = domain.get_symbol("a")
    b = domain.get_symbol("b")
    x = domain.get_symbol("x")
    y = domain.get_symbol("y")
    values = np.array([1, 1, 10, 20])

    def check(self, formula):
        return check(self.domain, formula, self.values)

    def test_ite(self):
        assert self.check(Ite(self.a, self.x, self.y)) == 10
        assert self.check(Ite(~self.a, self.x, self.y)) == 20

    def test_not(self):
        assert self.check(~self.a) is False

    def test_or(self):
        assert self.check(self.b | (self.x > 30)) is True

    def test_and(self):
        assert self.check(self.a & (self.x < 30)) is True

    def test_lt(self):
        assert self.check(self.x < 49) is True
        assert self.check(self.x < 10) is False

    def test_lte(self):
        assert self.check(self.x <= 49) is True
        assert self.check(self.x <= 10) is True
        assert self.check(self.x <= 9.0) is False

    def test_equals(self):
        assert self.check(Equals(self.x, Real(49))) is False
        assert self.check(Equals(self.x, Real(10))) is True

    def test_var_plus_var(self):
        assert self.check(self.x + self.y) == 30

    def test_var_plus_constant(self):
        assert self.check(self.x + 2) == 12

    def test_constant_plus_var(self):
        assert self.check(Real(3) + self.x) == 13

    def test_constant_plus_constant(self):
        assert self.check(Real(3) + Real(6)) == 9

    def test_var_minus_var(self):
        assert self.check(self.x - self.y) == -10

    def test_var_minus_constant(self):
        assert self.check(self.x - Real(2)) == 8

    def test_constant_minus_var(self):
        assert self.check(Real(3) - self.x) == -7

    def test_constant_minus_constant(self):
        assert self.check(Real(3) - Real(6)) == -3

    def test_var_times_var(self):
        assert self.check(self.x * self.y) == 200

    def test_var_times_constant(self):
        assert self.check(self.x * Real(2)) == 20

    def test_constant_times_var(self):
        assert self.check(Real(3) * self.x) == 30

    def test_constant_times_constant(self):
        assert self.check(Real(3) * Real(6)) == 18

    def test_var_pow_constant(self):
        assert self.check(Pow(self.x, Real(2))) == 100

    def test_constant_pow_constant(self):
        assert self.check(Pow(Real(3), Real(6))) == 729

    def test_symbol(self):
        assert self.check(self.a) is True
        assert self.check(self.b) is True
        assert self.check(self.x) == 10
        assert self.check(self.y) == 20

    def test_constant(self):
        assert self.check(Bool(True)) is True
        assert self.check(Real(5)) == 5
