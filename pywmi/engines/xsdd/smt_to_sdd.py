from .semiring import Semiring, amc
from pywmi.smt_math import get_inequality_smt, Polynomial

try:
    from pysdd.sdd import SddManager
except ImportError:
    SddManager = None

from pysmt.fnode import FNode
from pysmt.shortcuts import Real, Symbol, Pow, Plus, Times, get_type, LE, TRUE, FALSE, simplify
from pysmt.typing import REAL, BOOL
from pywmi import SmtWalker
from pywmi.errors import InstallError


def product(*elements):
    result = elements[0]
    for e in elements[1:]:
        result *= e
    return result


class SddConversionWalker(SmtWalker):
    def __init__(self, manager, abstractions=None, var_to_lit=None):
        self.manager = manager  # type: SddManager
        self.abstractions = abstractions if abstractions is not None else dict()
        self.var_to_lit = var_to_lit if var_to_lit is not None else dict()

    def new_literal(self):
        literal = self.manager.var_count() + 1
        self.manager.add_var_after_last()
        return literal

    def to_canonical(self, test_node):
        return get_inequality_smt(test_node)

    def test_to_sdd(self, test_node):
        test_node = self.to_canonical(test_node)
        # node_id = test_node.node_id()
        if test_node not in self.abstractions:
            literal = self.new_literal()
            self.abstractions[test_node] = literal
        return self.manager.l(self.abstractions[test_node])

    def to_dict(self, value_or_dict):
        if isinstance(value_or_dict, dict):
            return value_or_dict
        else:
            if not isinstance(value_or_dict, Polynomial):
                value_or_dict = Polynomial.from_smt(value_or_dict)
            return {value_or_dict: self.manager.true()}

    def dict_plus(self, dict1, dict2):
        if len(dict1) == 0:
            return dict2
        elif len(dict2) == 0:
            return dict1
        else:
            new_result = dict()
            for expression1, sdd1 in dict1.items():
                for expression2, sdd2 in dict2.items():
                    possibilities = [
                        (expression1, self.manager.conjoin(sdd1, sdd2.negate())),
                        (expression2, self.manager.conjoin(sdd1.negate(), sdd2)),
                        (expression1 + expression2, self.manager.conjoin(sdd1, sdd2)),
                    ]
                    for e, c in possibilities:
                        if not c.is_false():
                            new_result[e] = self.manager.disjoin(new_result.get(e, self.manager.false()), c)
            return new_result

    def dict_times(self, dict1, dict2):
        if len(dict1) == 0 or len(dict2) == 0:
            return dict()
        else:
            new_result = {}
            for expression1, sdd1 in dict1.items():
                for expression2, sdd2 in dict2.items():
                    sdd = self.manager.conjoin(sdd1, sdd2)
                    if not sdd.is_false() and expression1 != Real(0) and expression2 != Real(0):
                        if expression1 == Real(1):
                            e = expression2
                        elif expression2 == Real(1):
                            e = expression1
                        else:
                            e = expression1 * expression2
                        new_result[e] = self.manager.disjoin(new_result.get(e, self.manager.false()), sdd)
            return new_result

    def walk_and(self, args):
        converted = self.walk_smt_multiple(args)
        result = converted[0]
        for term in converted[1:]:
            result = self.manager.conjoin(result, term)
        return result

    def walk_or(self, args):
        converted = self.walk_smt_multiple(args)
        result = converted[0]
        for term in converted[1:]:
            result = self.manager.disjoin(result, term)
        return result

    def walk_plus(self, args):
        converted = self.walk_smt_multiple(args)
        if not any(isinstance(term, dict) for term in converted):
            new_terms = []
            if any(term.is_constant() for term in converted):
                new_terms.append(Real(sum(term.constant_value() for term in converted if term.is_constant())))
            new_terms += [term for term in converted if not term.is_constant()]
            if len(new_terms) == 1:
                return new_terms[0]
            else:
                return Plus(*new_terms)
        else:
            converted = [self.to_dict(term) for term in converted]
            result = converted[0]
            for term in converted[1:]:
                result = self.dict_plus(result, term)
            return result

    def walk_minus(self, left, right):
        left, right = self.walk_smt_multiple([left, right])

        if isinstance(right, dict):
            right = {Real(0) - expression: sdd for expression, sdd in right.items()}
        else:
            right = Real(0) - right

        if isinstance(left, dict) or isinstance(right, dict):
            return self.dict_plus(self.to_dict(left), self.to_dict(right))
        else:
            return left + right

    def walk_times(self, args):
        converted = self.walk_smt_multiple(args)
        if not any(isinstance(term, dict) for term in converted):
            new_terms = []
            if any(term.is_constant() for term in converted):
                new_terms.append(Real(product(term.constant_value() for term in converted if term.is_constant())))
            new_terms += [term for term in converted if not term.is_constant()]
            if len(new_terms) == 1:
                return new_terms[0]
            else:
                return Times(*new_terms)
        else:
            converted = [self.to_dict(term) for term in converted]
            result = converted[0]
            for term in converted[1:]:
                result = self.dict_times(result, term)
            return result

    def walk_not(self, argument):
        return self.manager.negate(self.walk_smt(argument))

    def walk_ite(self, if_arg, then_arg, else_arg):
        if get_type(then_arg) == BOOL:
            return self.walk_smt((if_arg & then_arg) | (~if_arg & else_arg))
        else:
            sdd, then_dict, else_dict = self.walk_smt_multiple([if_arg, then_arg, else_arg])
            print(self.dict_times({Polynomial.from_constant(1.0): sdd}, then_dict))
            print(self.dict_times({Polynomial.from_constant(1.0): sdd.negate()}, else_dict))
            return self.dict_plus(self.dict_times({Polynomial.from_constant(1.0): sdd}, then_dict),
                                  self.dict_times({Polynomial.from_constant(1.0): sdd.negate()}, else_dict))

    def walk_pow(self, base, exponent):
        return Pow(base, exponent)

    def walk_lte(self, left: FNode, right: FNode):
        return self.test_to_sdd(left <= right)

    def walk_lt(self, left: FNode, right: FNode):
        return self.test_to_sdd(left < right)

    def walk_equals(self, left, right):
        raise RuntimeError("Not supported")

    def walk_symbol(self, name, v_type):
        if v_type == REAL:
            return {Polynomial.from_smt(Symbol(name, REAL)): self.manager.true()}
        elif v_type == BOOL:
            if name not in self.var_to_lit:
                literal = self.new_literal()
                self.var_to_lit[name] = literal
            return self.manager.l(self.var_to_lit[name])

        raise ValueError(f"Unknown type {v_type}")

    def walk_constant(self, value, v_type):
        if v_type == REAL:
            return {Polynomial.from_smt(Real(value)): self.manager.true()}
        elif v_type == BOOL:
            if value:
                return self.manager.true()
            else:
                return self.manager.false()
        raise ValueError(f"Unknown type {v_type}")


class PySmtConversion(Semiring):
    def __init__(self, abstractions, var_to_lit):
        super()
        self.reverse_abstractions = {v: k for k, v in abstractions.items()}
        self.lit_to_var = {v: k for k, v in var_to_lit.items()}

    def times_neutral(self):
        return TRUE()

    def plus_neutral(self):
        return FALSE()

    def times(self, a, b, index=None):
        return a & b

    def plus(self, a, b, index=None):
        return a | b

    def negate(self, a):
        return ~a

    def positive_weight(self, a):
        return self.reverse_abstractions[a] if a in self.reverse_abstractions else Symbol(self.lit_to_var[a], BOOL)


def convert(formula, sdd_manager, abstractions=None, var_to_lit=None):
    if SddManager is None:
        raise InstallError("The pysdd package is required for this function but is not currently installed.")
    converter = SddConversionWalker(sdd_manager, abstractions, var_to_lit)
    return converter.walk_smt(formula)


def recover(sdd_node, abstractions, var_to_lit):
    return simplify(amc(PySmtConversion(abstractions, var_to_lit), sdd_node))