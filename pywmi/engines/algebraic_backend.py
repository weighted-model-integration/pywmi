from abc import ABC
from fractions import Fraction
from typing import Any, Dict, Tuple, List

import pysmt.shortcuts as smt
from pysmt.fnode import FNode
from pysmt.typing import REAL
import sympy

from pywmi.errors import InstallError
from pywmi import Domain

try:
    from ..weight_algebra.psi import psi
except InstallError:
    psi = None

E = Any


class AlgebraBackend(ABC):
    def zero(self) -> E:
        return self.real(0)

    def one(self) -> E:
        return self.real(1)

    def is_one(self, expression):
        raise NotImplementedError

    def is_zero(self, expression):
        raise NotImplementedError

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
        for _ in range(int(power)):
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


class PolynomialIntegrationBackend(AlgebraBackend, ABC):
    def __init__(self, exact=True):
        self.exact = exact

    def integrate_poly(
        self, expression, variables: List[str], bounds: Dict[str, Tuple[E, E]]
    ):
        raise NotImplementedError()

    @staticmethod
    def factor_list(weight):
        raise NotImplementedError


class IntegrationBackend(PolynomialIntegrationBackend, ABC):
    def __init__(self, exact=True):
        self.exact = exact

    def integrate(self, domain: Domain, expression, variables=None):
        raise NotImplementedError()

    def integrate_poly(
        self, expression, variables: List[str], bounds: Dict[str, Tuple[E, E]]
    ):
        symbols = [self.symbol(v) for v in variables]
        for var, sym in zip(variables, symbols):
            expression = self.times(
                self.greater_than_equal(sym, bounds[var][0]), expression
            )
            expression = self.times(
                self.less_than_equal(sym, bounds[var][1]), expression
            )

        result = self.integrate(None, expression, variables)
        return self.get_flat_expression(result)


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


class SympyAlgebra(PolynomialIntegrationBackend):
    def __init__(self):
        PolynomialIntegrationBackend.__init__(self, exact=True)

    def is_one(self, expression):
        expression.equal(1)

    def is_zero(self, expression):
        return expression.equals(0)

    def times(self, a, b):
        return a * b

    def plus(self, a, b):
        return a + b

    def negate(self, a):
        return -a

    def symbol(self, name):
        return sympy.S(name)

    def real(self, float_constant):
        assert isinstance(float_constant, (float, int, Fraction))
        if isinstance(float_constant, (Fraction, int)):
            return sympy.sympify(float_constant)
        else:
            fraction = Fraction.from_float(float_constant)
            return sympy.sympify(fraction)

    def to_float(self, real_value):
        if isinstance(real_value, sympy.Poly):
            real_value = sympy.simplify(real_value)
        return float(real_value)

    def integrate_poly(
        self, expression, variables: List[str], bounds: Dict[str, Tuple[E, E]]
    ):
        symbols = [self.symbol(v) for v in variables]
        result = expression
        for var, sym in zip(variables, symbols):
            lb, ub = bounds[var]
            result = self.integrate_single(result, sym, lb, ub)
        return result

    @staticmethod
    def integrate_single(expression, symbol, lb, ub):
        integrated = sympy.poly(expression, symbol).integrate()
        upper = integrated.subs(symbol, ub)
        lower = integrated.subs(symbol, lb)
        return upper - lower

    def get_variables(self, expression):
        return set([str(v) for v in expression.free_symbols])

    @staticmethod
    def factorize_list(weight):
        import sympy

        if not weight.free_symbols:
            return weight, []
        else:
            weight = weight.as_poly()
            weight = sympy.factor_list(weight)

            constant = weight[0]
            factor_list = []
            for f in weight[1]:
                factor_list.append(f[0] ** f[1])

            return constant, factor_list


class PsiPiecewisePolynomialAlgebra(IntegrationBackend):
    def __init__(self):
        IntegrationBackend.__init__(self, exact=True)
        if psi is None:
            raise InstallError(
                "PiecewisePolynomialAlgebra requires the psi library to be installed"
            )

    def is_one(self, expression):
        return expression.is_one

    def is_zero(self, expression):
        return expression.is_zero

    def times(self, a, b):
        return a * b

    def plus(self, a, b):
        return a + b

    def negate(self, a):
        return psi.PiecewisePolynomial(psi.S(-1)) * a

    def symbol(self, name):
        return psi.PiecewisePolynomial(psi.S(name))

    def symbolic_weight(self, weight):
        if isinstance(weight, psi.Polynomial):
            return psi.PiecewisePolynomial(weight.to_PsiExpr())
        else:
            raise NotImplementedError

    def real(self, float_constant):
        assert isinstance(float_constant, (float, int, Fraction))
        if isinstance(float_constant, Fraction):
            return psi.PiecewisePolynomial(psi.S("{}".format(float_constant)))
        elif isinstance(float_constant, int):
            return psi.PiecewisePolynomial(psi.S("{}".format(int(float_constant))))
        else:
            fraction = Fraction.from_float(float_constant)
            return psi.PiecewisePolynomial(
                psi.S("{}/{}".format(fraction.numerator, fraction.denominator))
            )

    def less_than(self, a, b):
        return a.lt(b)

    def less_than_equal(self, a, b):
        return a.le(b)

    def to_float(self, real_value):
        real_value = self.times(real_value, self.symbol(1.0))
        string_value = str(real_value.simplify())
        return float(string_value)

    def integrate(self, domain, expression, variables):
        for v in variables:
            var = self.symbol(v)
            expression = expression.integrate(var)
        return expression

    def get_weight_algebra(self):
        return PsiPolynomialAlgebra()


class PsiPolynomialAlgebra(PolynomialIntegrationBackend):
    def __init__(self):
        PolynomialIntegrationBackend.__init__(self, exact=True)
        if psi is None:
            raise InstallError(
                "PsiPolynomialAlgebra requires the psi library to be installed"
            )
        self._eval_bounds_cache = psi.EvalBoundsCache()

    def is_one(self, expression):
        return expression.is_one

    def is_zero(self, expression):
        return expression.is_zero

    def times(self, a, b):
        return a * b

    def plus(self, a, b):
        return a + b

    def negate(self, a):
        return psi.Polynomial(psi.S(-1)) * a

    def symbol(self, name):
        return psi.Polynomial(psi.S(name))

    def real(self, float_constant):
        assert isinstance(float_constant, (float, int, Fraction))
        if isinstance(float_constant, Fraction):
            return psi.Polynomial(psi.S("{}".format(float_constant)))
        elif isinstance(float_constant, int):
            return psi.Polynomial(psi.S("{}".format(int(float_constant))))
        else:
            fraction = Fraction.from_float(float_constant)
            return psi.Polynomial(
                psi.S("{}/{}".format(fraction.numerator, fraction.denominator))
            )

    def to_float(self, rational_value):
        rational_value = rational_value.simplify()
        try:
            return rational_value.to_float()
        except:
            rational_value = str(rational_value)
            num, den = rational_value.split("/")
            l_num = len(num)
            l_den = len(den)
            max_len = max(l_num, l_den)
            if l_num > l_den:
                num = num[:250]
                den = den[: 250 - (l_num - l_den)]
            else:
                num = num[: 250 - (l_den - l_num)]
                den = den[:250]
            return float(num) / float(den)

    def integrate_poly(
        self, expression, variables: List[str], bounds: Dict[str, Tuple[E, E]]
    ):
        symbols = [self.symbol(v) for v in variables]
        result = expression
        for var, sym in zip(variables, symbols):
            lb, ub = bounds[var]
            if self._eval_bounds_cache:
                result = result.integrate(sym, lb, ub, self._eval_bounds_cache)
            else:
                result = result.integrate(sym, lb, ub)
        return result

    def get_variables(self, expression):
        return set([str(v) for v in expression.variables])

    @staticmethod
    def factorize_list(weight):
        # TODO do this without sympy (lot of work)
        import sympy

        if not weight.variables:
            return weight, []
        else:
            weight = weight.simplify()
            weight = psi.toSympyString(weight)
            weight = weight.strip(",pZ,0,'+')").strip("limit(")

            weight = sympy.sympify(weight).as_poly()
            weight = sympy.factor_list(weight)

            def sympy2psi(expr):
                if type(expr) == sympy.Poly:
                    expr = expr.as_expr()

                if expr.is_constant() or expr.is_symbol:
                    return psi.S(str(expr))

                elif expr.is_Pow:
                    b = sympy2psi(expr.args[0])
                    e = sympy2psi(expr.args[1])
                    return b ** e
                elif expr.is_Add:
                    args = [sympy2psi(a) for a in expr.args]
                    result = psi.S(0)
                    for a in args:
                        result = result + a
                    return result.simplify()
                elif expr.is_Mul:
                    args = [sympy2psi(a) for a in expr.args]
                    result = psi.S(1)
                    for a in args:
                        result = result * a
                    return result.simplify()

            constant = psi.Polynomial(psi.S(str(weight[0])))
            factor_list = []
            for f in weight[1]:
                factor_list.append(
                    psi.Polynomial(sympy2psi(f[0]) ** psi.S(f[1])).simplify()
                )

            return constant, factor_list


class StringAlgebra(IntegrationBackend):
    def __init__(self):
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
        result = psi.pow(str(a), str(power))
        return result


class XaddAlgebra(IntegrationBackend):
    def __init__(self):
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
