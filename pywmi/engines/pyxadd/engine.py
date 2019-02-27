from typing import Optional

from pysmt.shortcuts import Symbol, Real, Bool, Times, Plus
from pysmt.typing import REAL, BOOL

from pywmi.engines.algebraic_backend import PSIAlgebra
from .resolve import ResolveIntegrator
from .operation import Summation, Multiplication, LogicalAnd, LogicalOr
from pywmi.engine import Engine
from pywmi.smt_walk import CachedSmtWalker
from .core import Pool
from .decision import Decision


class ToXaddWalker(CachedSmtWalker):
    def __init__(self, bool_mode, pool: Optional[Pool] = None):
        super().__init__(cache_key=self.key)
        self.bool_mode = bool_mode
        self.pool = pool or Pool()

    def key(self, f):
        return f, self.bool_mode

    def walk_and(self, args):
        assert self.bool_mode
        result = self.pool.one_id
        for arg in self.walk_smt_multiple(args):
            result = self.pool.apply(LogicalAnd, result, arg)
        return result

    def walk_or(self, args):
        assert self.bool_mode
        result = self.pool.zero_id
        for arg in self.walk_smt_multiple(args):
            result = self.pool.apply(LogicalOr, result, arg)
        return result

    def walk_plus(self, args):
        if self.bool_mode:
            return Plus(*args)
        else:
            result = self.pool.zero_id
            for arg in self.walk_smt_multiple(args):
                result = self.pool.apply(Summation, result, arg)
            return result

    def walk_minus(self, left, right):
        return self.walk_smt(left + (right * -1))

    def walk_times(self, args):
        assert len(args) > 0
        if self.bool_mode:
            return Times(*args)
        else:
            result = self.pool.one_id
            for arg in self.walk_smt_multiple(args):
                result = self.pool.apply(Multiplication, result, arg)
            return result

    def walk_not(self, argument):
        assert self.bool_mode
        return self.pool.invert(self.walk_smt(argument))

    def walk_ite(self, if_arg, then_arg, else_arg):
        if self.bool_mode:
            return self.walk_smt((if_arg & then_arg) | (~if_arg & else_arg))
        else:
            self.bool_mode = True
            if_xadd = self.walk_smt(if_arg)
            self.bool_mode = False
            then_xadd, else_xadd = self.walk_smt_multiple([then_arg, else_arg])
            return self.pool.apply(Summation, self.pool.apply(Multiplication, if_xadd, then_xadd),
                                   self.pool.apply(Multiplication, self.pool.invert(if_xadd), else_xadd))

    def walk_pow(self, base, exponent):
        base, = self.walk_smt_multiple([base])
        exponent = exponent.constant_value()
        assert int(exponent) == exponent
        exponent = int(exponent)
        if exponent == 0:
            return self.pool.one_id
        else:
            result = base
            for i in range(exponent - 1):
                result = self.pool.apply(Multiplication, result, base)
            return result

    def walk_lte(self, left, right):
        assert self.bool_mode
        left, right = self.walk_smt_multiple([left, right])
        return self.pool.bool_test(Decision(left <= right))

    def walk_lt(self, left, right):
        # noinspection PyTypeChecker
        return self.walk_smt(left <= right)

    def walk_equals(self, left, right):
        raise NotImplementedError()

    def walk_symbol(self, name, v_type):
        if self.bool_mode:
            symbol = Symbol(name, v_type)
            if v_type == BOOL:
                return self.pool.bool_test(Decision(symbol))
            return symbol
        else:
            return self.pool.terminal(self.pool.algebra.symbol(name))

    def walk_constant(self, value, v_type):
        if self.bool_mode:
            return Real(value) if v_type == REAL else self.pool.bool_test(Decision(Bool(value)))
        else:
            assert v_type != BOOL
            return self.pool.terminal(self.pool.algebra.real(float(value)))


class PyXaddEngine(Engine):
    def __init__(self, domain=None, support=None, weight=None, pool: Optional[Pool] = None, reduce_strategy=None):
        super().__init__(domain, support, weight, True)
        self.pool = pool or Pool(algebra=PSIAlgebra())
        self.reduce_strategy = reduce_strategy

    def compute_volume(self, add_bounds=True):
        support = self.support
        if add_bounds:
            support = support & self.domain.get_bounds()
        theory_xadd = ToXaddWalker(True, self.pool).walk_smt(support)
        weight_xadd = ToXaddWalker(False, self.pool).walk_smt(self.weight)
        combined = self.pool.apply(Multiplication, theory_xadd, weight_xadd)
        integrator = ResolveIntegrator(self.pool, reduce_strategy=self.reduce_strategy)
        result = combined
        for v in self.domain.get_symbols():
            result = integrator.integrate(result, v)
        result_node = self.pool.get_node(result)
        assert result_node.is_terminal()
        return self.pool.algebra.to_float(result_node.expression)

    def copy(self, domain, support, weight):
        return PyXaddEngine(domain, support, weight, pool=self.pool, reduce_strategy=self.reduce_strategy)
