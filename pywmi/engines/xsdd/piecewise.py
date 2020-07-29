
from typing import Dict, Any
from itertools import product
from functools import reduce
from operator import mul, add
from pysmt.fnode import FNode
from pysmt.environment import Environment
from pysmt.typing import BOOL, REAL

from pywmi.smt_walk import CachedSmtWalker
from pywmi.engines.algebraic_backend import AlgebraBackend


class PiecewiseFunction:
    def __init__(self, pieces: Dict[Any, FNode], algebra: AlgebraBackend, env: Environment):
        self.pieces = pieces  # expression -> support
        self.algebra = algebra
        self.env = env
        self.fm = env.formula_manager

    def empty(self):
        return len(self.pieces) == 0

    def assert_related(self, other):
        assert isinstance(other, PiecewiseFunction)
        assert other.algebra == self.algebra
        assert other.env == self.env

    def shortcuts(self):
        return self.fm.And, self.fm.Or, self.fm.Not, self.env.simplifier.simplify

    def __add__(self, other):
        self.assert_related(other)
        And, Or, Not, simplify = self.shortcuts()

        if self.empty():
            return other
        elif other.empty():
            return self
        else:
            new_pieces = {}
            for (expr1, sup1), (expr2, sup2) in product(self.pieces.items(), other.pieces.items()):
                possibilities = [
                    (expr1, simplify(And(sup1, Not(sup2)))),
                    (expr2, simplify(And(Not(sup1), sup2))),
                    (self.algebra.plus(expr1, expr2), simplify(And(sup1, sup2))),
                ]
                for e, c in possibilities:
                    # TODO check if c is satisfiable at all?
                    # used to be done by actually compiling SDD, currently through smt.simplify
                    # TODO: this used to be `e == zero`, but that seems wrong?
                    if not c.is_false() and e != self.algebra.zero():
                        new_pieces[e] = simplify(Or(new_pieces.get(e, self.fm.FALSE()), c))
            return PiecewiseFunction(new_pieces, self.algebra, self.env)

    def __mul__(self, other):
        self.assert_related(other)
        And, Or, Not, simplify = self.shortcuts()

        new_pieces = {}
        for (expr1, sup1), (expr2, sup2) in product(self.pieces.items(), other.pieces.items()):
            sup = simplify(And(sup1, sup2))
            zero = self.algebra.zero()
            one = self.algebra.one()

            # TODO check if sup is satisfiable
            if expr1 != zero and expr2 != zero:
                if expr1 == one:
                    e = expr2
                elif expr2 == one:
                    e = expr1
                else:
                    e = self.algebra.times(expr1, expr2)
                if e != zero:
                    new_pieces[e] = simplify(Or(new_pieces.get(e, self.fm.FALSE()), sup))
        return PiecewiseFunction(new_pieces, self.algebra, self.env)

    def __neg__(self):
        new_pieces = {self.algebra.negate(expr): sup
                      for expr, sup in self.pieces.items()}
        return PiecewiseFunction(new_pieces, self.algebra, self.env)

    def condition(self, condition):
        new_pieces = {expr: self.fm.And(sup, condition)
                      for expr, sup in self.pieces.items()}
        return PiecewiseFunction(new_pieces, self.algebra, self.env)

    def __str__(self):
        return f"PWF({len(self.pieces)})"

    __repr__ = __str__

    @staticmethod
    def ite(condition, then_expression, else_expression, env):
        assert isinstance(condition, FNode)
        assert isinstance(then_expression, PiecewiseFunction)
        assert isinstance(else_expression, PiecewiseFunction)

        return then_expression.condition(condition) + else_expression.condition(env.formula_manager.Not(condition))

    @staticmethod
    def symbol(name, algebra: AlgebraBackend, env: Environment):
        pieces = {algebra.symbol(name): env.formula_manager.TRUE()}
        return PiecewiseFunction(pieces, algebra, env)

    @staticmethod
    def real(float_constant, algebra: AlgebraBackend, env: Environment, convert=True):
        if convert:
            float_constant = algebra.real(float_constant)
        pieces = {float_constant: env.formula_manager.TRUE()}
        return PiecewiseFunction(pieces, algebra, env)


class PiecewiseFunctionConverter(CachedSmtWalker):
    def __init__(self, algebra, env):
        super().__init__()
        self.algebra = algebra
        self.env = env
        self.boolean_stack = [False]

    def assert_boolean_parse_mode(self, boolean):
        if boolean != self.boolean_stack[-1]:
            raise ValueError("Parsing mode must be " + ("" if boolean else "non-") + "boolean")

    def walk_and(self, args):
        self.assert_boolean_parse_mode(True)
        converted = self.walk_smt_multiple(args)
        return self.env.formula_manager.And(converted)

    def walk_or(self, args):
        self.assert_boolean_parse_mode(True)
        converted = self.walk_smt_multiple(args)
        return self.env.formula_manager.Or(converted)

    def walk_plus(self, args):
        self.assert_boolean_parse_mode(False)
        converted = self.walk_smt_multiple(args)
        return reduce(add, converted)

    def walk_minus(self, left, right):
        self.assert_boolean_parse_mode(False)
        left, right = self.walk_smt_multiple([left, right])
        return left + (~right)

    def walk_times(self, args):
        self.assert_boolean_parse_mode(False)
        converted = self.walk_smt_multiple(args)
        return reduce(mul, converted)

    def walk_not(self, arg):
        self.assert_boolean_parse_mode(True)
        return self.env.formula_manager.Not(self.walk_smt(arg))

    def walk_ite(self, if_arg, then_arg, else_arg):
        if self.boolean_stack[-1]:
            fm = self.env.formula_manager
            formula = fm.Or(fm.And(if_arg, then_arg), fm.And(fm.Not(if_arg), else_arg))
            return self.walk_smt(formula)

        then_expr, else_expr = self.walk_smt_multiple([then_arg, else_arg])
        # TODO(evert): Right now, click graph is REALLY slow
        # Which is an improvement from what it was before: not working at all
        # Either way, it seems more likely I'm doing something wrong
        # (there are many, many pieces!)
        return PiecewiseFunction.ite(if_arg, then_expr, else_expr, self.env)

    def walk_pow(self, base, exponent):
        base = self.walk_smt(base)
        exponent = exponent.constant_value()
        assert int(exponent) == exponent
        if exponent == 0:
            return PiecewiseFunction.real(1, self.algebra, self.env)
        return reduce(mul, [base]*int(exponent))

    # Everything below just passes through stuff (while checking parse mode)

    def _walk_comparison(self, left, right, comparison_factory):
        self.assert_boolean_parse_mode(True)
        self.boolean_stack.append(False)
        # TODO(evert): We can't really build a comparison from PiecewiseFunctions
        # so this is basically just a crapshoot...
        res = comparison_factory(self.walk_smt(left), self.walk_smt(right))
        self.boolean_stack.pop()
        return res

    def walk_lte(self, left, right):
        return self._walk_comparison(left, right, self.env.formula_manager.LE)

    def walk_lt(self, left, right):
        return self._walk_comparison(left, right, self.env.formula_manager.LT)

    def walk_equals(self, left, right):
        raise RuntimeError("Not supported")

    def walk_symbol(self, name, v_type):
        if self.boolean_stack[-1]:
            if v_type != BOOL:
                raise ValueError("Parsing mode cannot be boolean")
            return self.env.formula_manager.Symbol(name, typename=BOOL)
        else:
            if v_type != REAL:
                raise ValueError("Parsing mode cannot be real")
            return PiecewiseFunction.symbol(name, self.algebra, self.env)

    def walk_constant(self, value, v_type):
        if self.boolean_stack[-1]:
            if v_type != BOOL:
                raise ValueError("Parsing mode cannot be boolean")
            return self.env.formula_manager.Bool(value)
        else:
            if v_type != REAL:
                raise ValueError("Parsing mode cannot be real")
            return PiecewiseFunction.real(value, self.algebra, self.env)


def split_up_function(function, algebra, env):
    pw_converter = PiecewiseFunctionConverter(algebra, env)
    return pw_converter.walk_smt(function)
