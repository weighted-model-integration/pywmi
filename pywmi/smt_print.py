from .smt_math import LinearInequality
from .smt_walk import SmtWalker
import pysmt.shortcuts as smt


class PrintWalker(SmtWalker):
    def walk_and(self, args):
        return "(" + " & ".join(self.walk_smt(p) for p in args) + ")"

    def walk_or(self, args):
        return "(" + " | ".join(self.walk_smt(p) for p in args) + ")"

    def walk_plus(self, args):
        args = [self.walk_smt(p) for p in args]
        if all(arg == "0" for arg in args):
            return "0"
        args = [arg for arg in args if arg != "0"]
        return " + ".join(args)

    def walk_minus(self, left, right):
        return "{} - {}".format(*[self.walk_smt(p) for p in [left, right]])

    def walk_times(self, args):
        args = [self.walk_smt(p) for p in args]
        if any(arg == "0" for arg in args):
            return "0"
        if all(arg == "1" for arg in args):
            return "1"
        args = [arg for arg in args if arg != "1"]
        return "*".join(args)

    def walk_not(self, argument):
        return "~{}".format(self.walk_smt(argument))

    def walk_ite(self, if_arg, then_arg, else_arg):
        return "(if {} then {} else {})".format(*[self.walk_smt(p) for p in [if_arg, then_arg, else_arg]])

    def walk_pow(self, base, exponent):
        return "{}^{}".format(*[self.walk_smt(p) for p in [base, exponent]])

    def walk_lte(self, left, right):
        inequality = LinearInequality.from_smt(left <= right).normalize().to_smt()
        left, right = [self.walk_smt(p) for p in inequality.args()]
        return "({} <= {})".format(left, right)

    def walk_lt(self, left, right):
        inequality = LinearInequality.from_smt(left <= right).normalize().to_smt()
        left, right = [self.walk_smt(p) for p in inequality.args()]
        return "({} < {})".format(left, right)

    def walk_equals(self, left, right):
        return "({} = {})".format(*[self.walk_smt(p) for p in [left, right]])

    def walk_symbol(self, name, v_type):
        return name

    def walk_constant(self, value, v_type):
        if v_type == smt.BOOL:
            return str(value)
        elif v_type == smt.REAL:
            if int(value) == float(value):
                value = int(value)
            else:
                value = float(value)
            return "{}".format(value)
        else:
            raise RuntimeError("Unknown type {}".format(v_type))


def pretty_print(formula):
    return PrintWalker().walk_smt(formula)


def pretty_print_instance(domain, values):
    return ", ".join("{}: {}".format(var, values[i]) for i, var in enumerate(domain.variables))
