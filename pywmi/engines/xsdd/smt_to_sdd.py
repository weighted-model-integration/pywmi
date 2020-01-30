from typing import Tuple, Dict, Optional

from pywmi.engines.algebraic_backend import AlgebraBackend
from pywmi.engines.xsdd.piecewise import PiecewiseXSDD
from pywmi.smt_math import LinearInequality
from .semiring import Semiring, amc

try:
    from pysdd.sdd import SddManager, SddNode
except ImportError:
    SddManager = None
    SddNode = None

from pysmt.fnode import FNode
from pysmt.shortcuts import Symbol, TRUE, FALSE, simplify, Times
from pysmt.typing import REAL, BOOL
from pywmi.smt_walk import CachedSmtWalker
from pywmi.errors import InstallError


def product(*elements):
    result = elements[0]
    for e in elements[1:]:
        result *= e
    return result


class SddConversionWalker(CachedSmtWalker):
    def __init__(self, manager, algebra: AlgebraBackend, boolean_only, abstractions=None, var_to_lit=None):
        super().__init__()
        self.manager = manager  # type: SddManager
        self.algebra = algebra
        self.abstractions = abstractions if abstractions is not None else dict()
        self.var_to_lit = var_to_lit if var_to_lit is not None else dict()
        self.boolean_stack = [boolean_only]

    def new_literal(self):
        literal = self.manager.var_count() + 1
        self.manager.add_var_after_last()
        return literal

    def to_canonical(self, test_node):
        # TODO Use LinearInequality instead?

        return LinearInequality.from_smt(test_node).normalize().to_smt()
        # return get_inequality_smt(test_node)

    def test_to_sdd(self, test_node):
        test_node = self.to_canonical(test_node)
        negate = False
        if test_node.arg(1).constant_value() == -1:
            test_node = self.to_canonical(test_node.arg(0) >= test_node.arg(1))
            negate = True
        # node_id = test_node.node_id()
        if test_node not in self.abstractions:
            literal = self.new_literal()
            self.abstractions[test_node] = literal
        result = self.manager.l(self.abstractions[test_node])
        if negate:
            result = result.negate()
        return result

    def walk_and(self, args):
        if not self.boolean_stack[-1]:
            raise ValueError("Parsing mode must be boolean")
        converted = self.walk_smt_multiple(args)

        result = converted[0]
        for term in converted[1:]:
            result = self.manager.conjoin(result, term)
        return result

    def walk_or(self, args):
        if not self.boolean_stack[-1]:
            raise ValueError("Parsing mode must be boolean")
        converted = self.walk_smt_multiple(args)

        result = converted[0]
        for term in converted[1:]:
            result = self.manager.disjoin(result, term)
        return result

    def walk_plus(self, args):
        if self.boolean_stack[-1]:
            raise ValueError("Parsing mode must be non-boolean")
        converted = self.walk_smt_multiple(args)
        result = converted[0]
        for c in converted[1:]:
            result += c
        return result

    def walk_minus(self, left, right):
        if self.boolean_stack[-1]:
            raise ValueError("Parsing mode must be non-boolean")

        left, right = self.walk_smt_multiple([left, right])

        return left + (~right)

    def walk_times(self, args):
        if self.boolean_stack[-1]:
            raise ValueError("Parsing mode must be non-boolean")
        converted = self.walk_smt_multiple(args)

        result = converted[0]
        for c in converted[1:]:
            result *= c
        return result

    def walk_not(self, argument):
        if not self.boolean_stack[-1]:
            raise ValueError("Parsing mode must be boolean")

        return self.manager.negate(self.walk_smt(argument))

    def walk_ite(self, if_arg, then_arg, else_arg):
        if self.boolean_stack[-1]:
            return self.walk_smt((if_arg & then_arg) | (~if_arg & else_arg))

        self.boolean_stack.append(True)
        sdd = self.walk_smt(if_arg)
        self.boolean_stack[-1] = False
        then_expression, else_expression = self.walk_smt_multiple([then_arg, else_arg])
        self.boolean_stack.pop()

        return PiecewiseXSDD.ite(sdd, then_expression, else_expression)

    def walk_pow(self, base, exponent):
        base, = self.walk_smt_multiple([base])
        exponent = exponent.constant_value()
        assert int(exponent) == exponent
        exponent = int(exponent)
        if exponent == 0:
            return PiecewiseXSDD.real(1, self.manager, self.algebra)
        result = base
        for i in range(exponent - 1):
            result *= base
        return result

    def walk_lte(self, left: FNode, right: FNode):
        if not self.boolean_stack[-1]:
            raise ValueError("Parsing mode must be boolean")

        return self.test_to_sdd(left <= right)

    def walk_lt(self, left: FNode, right: FNode):
        if not self.boolean_stack[-1]:
            raise ValueError("Parsing mode must be boolean")

        return self.test_to_sdd(left < right)

    def walk_equals(self, left, right):
        raise RuntimeError("Not supported")

    def walk_symbol(self, name, v_type):
        if self.boolean_stack[-1]:
            if v_type != BOOL:
                raise ValueError("Parsing mode cannot be boolean")
            if name not in self.var_to_lit:
                literal = self.new_literal()
                self.var_to_lit[name] = literal
            return self.manager.l(self.var_to_lit[name])
        else:
            if v_type != REAL:
                raise ValueError("Parsing mode cannot be real")
            return PiecewiseXSDD.symbol(name, self.manager, self.algebra)

    def walk_constant(self, value, v_type):
        if self.boolean_stack[-1]:
            if v_type != BOOL:
                raise ValueError("Parsing mode cannot be boolean")
            if value:
                return self.manager.true()
            else:
                return self.manager.false()
        else:
            if v_type != REAL:
                raise ValueError("Parsing mode cannot be real")
            return PiecewiseXSDD.real(value, self.manager, self.algebra)


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


def convert_formula(formula, sdd_manager, algebra: AlgebraBackend, abstractions=None, var_to_lit=None)\
        -> SddNode:
    if SddManager is None:
        raise InstallError("The pysdd package is required for this function but is not currently installed.")
    converter = SddConversionWalker(sdd_manager, algebra, True, abstractions, var_to_lit)
    return converter.walk_smt(formula)


def convert_function(formula, sdd_manager, algebra: AlgebraBackend, abstractions=None, var_to_lit=None)\
        -> PiecewiseXSDD:
    if SddManager is None:
        raise InstallError("The pysdd package is required for this function but is not currently installed.")
    converter = SddConversionWalker(sdd_manager, algebra, False, abstractions, var_to_lit)
    return converter.walk_smt(formula)


def recover_formula(sdd_node: SddNode, abstractions, var_to_lit, simplify_result=True) -> FNode:
    result = amc(PySmtConversion(abstractions, var_to_lit), sdd_node)
    return simplify(result) if simplify_result else result


def get_bool_label(formula: FNode) -> Optional[Tuple[str, FNode, FNode]]:
    if formula.is_ite():
        c, t, e = formula.args()  # type: FNode
        if c.is_symbol() and c.symbol_type() == BOOL:
            return c.symbol_name(), t, e
    return None


label_dict_type = Dict[str, Tuple[FNode, FNode]]


def extract_labels_and_weight(weight: FNode) -> Tuple[label_dict_type, FNode]:
    labels = dict()
    terms = []
    if weight.is_times():
        for arg in weight.args():  # type: FNode
            label = get_bool_label(arg)
            if label is not None:
                labels[label[0]] = tuple(label[1:])
            else:
                terms.append(arg)
        return labels, Times(*terms)
    else:
        return labels, weight
