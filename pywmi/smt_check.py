import numpy as np
import pysmt.shortcuts as smt

from smt_walk import SmtWalker


class SmtChecker(SmtWalker):
    def __init__(self, assignment):
        self.assignment = assignment

    def walk_plus(self, args):
        return sum(self.walk_smt_multiple(args))

    def walk_minus(self, left, right):
        return self.walk_smt(left) - self.walk_smt(right)

    def walk_lt(self, left, right):
        return self.walk_smt(left) < self.walk_smt(right)

    def walk_ite(self, if_arg, then_arg, else_arg):
        return self.walk_smt(then_arg) if self.walk_smt(if_arg) else self.walk_smt(else_arg)

    def walk_and(self, args):
        return all(self.walk_smt_multiple(args))

    def walk_symbol(self, name, v_type):
        return self.walk_constant(self.assignment[name], v_type)

    def walk_constant(self, value, v_type):
        if v_type == smt.BOOL:
            if isinstance(value, bool):
                return bool(value)
            return bool(value.constant_value())
        elif v_type == smt.REAL:
            try:
                return float(value)
            except TypeError:
                return float(value.constant_value())
        raise RuntimeError("Unsupported type {}".format(v_type))

    def walk_lte(self, left, right):
        return self.walk_smt(left) <= self.walk_smt(right)

    def walk_equals(self, left, right):
        return self.walk_smt(left) == self.walk_smt(right)

    def walk_or(self, args):
        return any(self.walk_smt_multiple(args))

    def walk_pow(self, base, exponent):
        return self.walk_smt(base) ** self.walk_smt(exponent)

    def walk_times(self, args):
        if len(args) > 0:
            aggregate = 1
            for res in self.walk_smt_multiple(args):
                aggregate *= res
            return aggregate
        raise RuntimeError("Zero argument multiplication")

    def walk_not(self, argument):
        return not self.walk_smt(argument)

    def check(self, formula):
        return self.walk_smt(formula)


class SmtBatchChecker(SmtWalker):
    def __init__(self, domain, boolean_values, real_values):
        self.boolean_values = boolean_values
        self.real_values = real_values
        self.length = self.boolean_values.size[0]
        if self.length != self.real_values.size[0]:
            raise ValueError("Boolean and real values must contain an equal number of rows (was {} and {})"
                             .format(self.boolean_values.size[0], self.real_values.size[0]))
        self.boolean_indices = {v: i for i, v in enumerate(domain.bool_vars)}
        self.real_indices = {v: i for i, v in enumerate(domain.real_vars)}

    def walk_ite(self, if_arg, then_arg, else_arg):
        if_samples, then_samples, else_samples = self.walk_smt_multiple([if_arg, then_arg, else_arg])
        return np.where(if_samples, then_samples, else_samples)

    def walk_not(self, argument):
        return np.logical_not(self.walk_smt(argument))

    def walk_or(self, args):
        args = self.walk_smt_multiple(args)
        result = args[0]
        for i in range(1, len(args)):
            result |= args[i]
        return result

    def walk_and(self, args):
        args = self.walk_smt_multiple(args)
        result = args[0]
        for i in range(1, len(args)):
            result &= args[i]
        return result

    def walk_lt(self, left, right):
        return self.walk_smt(left) < self.walk_smt(right)

    def walk_lte(self, left, right):
        return self.walk_smt(left) <= self.walk_smt(right)

    def walk_equals(self, left, right):
        return self.walk_smt(left) == self.walk_smt(right)

    def walk_plus(self, args):
        return sum(self.walk_smt_multiple(args))

    def walk_minus(self, left, right):
        return self.walk_smt(left) - self.walk_smt(right)

    def walk_times(self, args):
        if len(args) > 0:
            aggregate = 1
            for res in self.walk_smt_multiple(args):
                aggregate *= res
            return aggregate
        raise RuntimeError("Zero argument multiplication")

    def walk_pow(self, base, exponent):
        return self.walk_smt(base) ** self.walk_smt(exponent)

    def walk_symbol(self, name, v_type):
        if v_type == smt.BOOL:
            return self.boolean_values[:, self.boolean_indices[name]]
        elif v_type == smt.REAL:
            return self.real_values[:, self.real_indices[name]]
        raise RuntimeError("Unsupported type {}".format(v_type))

    def walk_constant(self, value, v_type):
        if v_type == smt.BOOL:
            return np.full(self.length, bool(value))
        elif v_type == smt.REAL:
            return np.full(self.length, float(value))
        raise RuntimeError("Unsupported type {}".format(v_type))

    def check(self, formula):
        return self.walk_smt(formula)


class SmtSingleChecker(SmtWalker):
    def __init__(self, domain, boolean_values, real_values):
        self.boolean_values = boolean_values
        self.real_values = real_values
        self.boolean_indices = {v: i for i, v in enumerate(domain.bool_vars)}
        self.real_indices = {v: i for i, v in enumerate(domain.real_vars)}

    def walk_ite(self, if_arg, then_arg, else_arg):
        if_val, then_val, else_val = self.walk_smt_multiple([if_arg, then_arg, else_arg])
        return then_val if if_val else else_val

    def walk_not(self, argument):
        return not self.walk_smt(argument)

    def walk_or(self, args):
        return any(self.walk_smt_multiple(args))

    def walk_and(self, args):
        return all(self.walk_smt_multiple(args))

    def walk_lt(self, left, right):
        return self.walk_smt(left) < self.walk_smt(right)

    def walk_lte(self, left, right):
        return self.walk_smt(left) <= self.walk_smt(right)

    def walk_equals(self, left, right):
        return self.walk_smt(left) == self.walk_smt(right)

    def walk_plus(self, args):
        return sum(self.walk_smt_multiple(args))

    def walk_minus(self, left, right):
        return self.walk_smt(left) - self.walk_smt(right)

    def walk_times(self, args):
        if len(args) > 0:
            aggregate = 1
            for res in self.walk_smt_multiple(args):
                aggregate *= res
            return aggregate
        raise RuntimeError("Zero argument multiplication")

    def walk_pow(self, base, exponent):
        return self.walk_smt(base) ** self.walk_smt(exponent)

    def walk_symbol(self, name, v_type):
        if v_type == smt.BOOL:
            return self.boolean_values[self.boolean_indices[name]]
        elif v_type == smt.REAL:
            return self.real_values[self.real_indices[name]]
        raise RuntimeError("Unsupported type {}".format(v_type))

    def walk_constant(self, value, v_type):
        if v_type == smt.BOOL:
            return bool(value)
        elif v_type == smt.REAL:
            return float(value)
        raise RuntimeError("Unsupported type {}".format(v_type))

    def check(self, formula):
        return self.walk_smt(formula)


def test_assignment(formula, assignment):
    return SmtChecker(assignment).walk_smt(formula)


def test(domain, formula, boolean_values, real_values):
    if boolean_values.ndim == 1 and real_values.ndim == 1:  # TODO Test if which dimension, but is tough
        return SmtSingleChecker(domain, boolean_values, real_values).walk_smt(formula)
    return SmtBatchChecker(domain, boolean_values, real_values).walk_smt(formula)
