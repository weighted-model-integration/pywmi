from pysmt.fnode import FNode

from pywmi import SmtWalker
import pysmt.shortcuts as smt

from pywmi.smt_math import LinearInequality


class NormalizationWalker(SmtWalker):
    def walk_and(self, args):
        return smt.And(*self.walk_smt_multiple(args))

    def walk_or(self, args):
        return smt.Or(*self.walk_smt_multiple(args))

    def walk_plus(self, args):
        return smt.Plus(*self.walk_smt_multiple(args))

    def walk_minus(self, left, right):
        return self.walk_smt(left) - self.walk_smt(right)

    def walk_times(self, args):
        return smt.Times(*self.walk_smt_multiple(args))

    def walk_not(self, argument):
        return smt.Not(self.walk_smt(argument))

    def walk_ite(self, if_arg, then_arg, else_arg):
        return smt.Ite(self.walk_smt(if_arg), self.walk_smt(then_arg), self.walk_smt(else_arg))

    def walk_pow(self, base, exponent):
        return smt.Pow(self.walk_smt(base), self.walk_smt(exponent))

    def walk_lte(self, left, right):
        return LinearInequality.from_smt(left <= right).normalize().to_smt()

    def walk_lt(self, left, right):
        return LinearInequality.from_smt(left < right).normalize().to_smt()

    def walk_equals(self, left, right):
        return smt.Equals(self.walk_smt(left), self.walk_smt(right))

    def walk_symbol(self, name, v_type):
        return smt.Symbol(name, v_type)

    def walk_constant(self, value, v_type):
        if v_type == smt.BOOL:
            return smt.Bool(value)
        elif v_type == smt.REAL:
            return smt.Real(value)
        else:
            return ValueError("Unknown type {}".format(v_type))


def normalize_formula(formula):
    # type: (FNode) -> FNode
    return NormalizationWalker().walk_smt(formula)
