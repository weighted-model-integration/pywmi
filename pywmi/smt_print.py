from .smt_math import LinearInequality
from .smt_walk import SmtWalker
import pysmt.shortcuts as smt


class PrintWalker(SmtWalker):
    def __init__(self, rounding=None):
        self.rounding = rounding

    def walk_and(self, args):
        return "(" + " & ".join(self.walk_smt(p) for p in args) + ")"

    def walk_or(self, args):
        return "(" + " | ".join(self.walk_smt(p) for p in args) + ")"

    def walk_plus(self, args):
        args = [self.walk_smt(p) for p in args]
        if all(arg == "0" for arg in args):
            return "0"
        args = [arg for arg in args if arg != "0"]
        result = args[0]
        for arg in args[1:]:
            if arg.startswith("-"):
                result += " - " + arg[1:]
            else:
                result += " + " + arg
        return result

    def walk_minus(self, left, right):
        return "{} - {}".format(*[self.walk_smt(p) for p in [left, right]])

    def walk_times(self, args):
        args = [self.walk_smt(p) for p in args]
        if any(arg == "0" for arg in args):
            return "0"
        if all(arg == "1" for arg in args):
            return "1"
        args = [arg for arg in args if arg != "1"]
        sign = sum(1 if arg[0] == "-" else 0 for arg in args) % 2
        args = [arg[1:] if arg[0] == "-" else arg for arg in args if arg != "1"]
        args = sorted(args, key=lambda x: (0 if any(x.startswith(d) for d in "0123456789") else 1))
        return ("-" if sign == 1 else "") + "*".join(args)

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
                if self.rounding:
                    value = "{:.{r}f}".format(value, r=self.rounding)
            return "{}".format(value)
        else:
            raise RuntimeError("Unknown type {}".format(v_type))


def pretty_print(formula, rounding=None):
    return PrintWalker(rounding).walk_smt(formula)


def pretty_print_instance(domain, values):
    return ", ".join("{}: {}".format(var, values[i]) for i, var in enumerate(domain.variables))
