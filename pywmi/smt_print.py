from .smt_walk import SmtWalker
import pysmt.shortcuts as smt


class PrintWalker(SmtWalker):
    def walk_and(self, args):
        return "(" + " & ".join(self.walk_smt(p) for p in args) + ")"

    def walk_or(self, args):
        return "(" + " | ".join(self.walk_smt(p) for p in args) + ")"

    def walk_plus(self, args):
        return " + ".join(self.walk_smt(p) for p in args)

    def walk_minus(self, left, right):
        return "{} - {}".format(*[self.walk_smt(p) for p in [left, right]])

    def walk_times(self, args):
        return "*".join(self.walk_smt(p) for p in args)

    def walk_not(self, argument):
        return "~{}".format(self.walk_smt(argument))

    def walk_ite(self, if_arg, then_arg, else_arg):
        return "(if {} then {} else {})".format(*[self.walk_smt(p) for p in [if_arg, then_arg, else_arg]])

    def walk_pow(self, base, exponent):
        return "{}^{}".format(*[self.walk_smt(p) for p in [base, exponent]])

    def walk_lte(self, left, right):
        return "({} <= {})".format(*[self.walk_smt(p) for p in [left, right]])

    def walk_lt(self, left, right):
        return "({} < {})".format(*[self.walk_smt(p) for p in [left, right]])

    def walk_equals(self, left, right):
        return "({} = {})".format(*[self.walk_smt(p) for p in [left, right]])

    def walk_symbol(self, name, v_type):
        return name

    def walk_constant(self, value, v_type):
        if v_type == smt.BOOL:
            return str(value)
        elif v_type == smt.REAL:
            return "{}".format(float(value))
        else:
            raise RuntimeError("Unknown type {}".format(v_type))


def pretty_print(formula):
    return PrintWalker().walk_smt(formula)


def pretty_print_instance(domain, values):
    return ", ".join("{}: {}".format(var, values[i]) for i, var in enumerate(domain.variables))
