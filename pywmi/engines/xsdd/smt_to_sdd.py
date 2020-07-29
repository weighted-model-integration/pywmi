from typing import Tuple, Dict, Optional, Any
from functools import reduce

from pysmt.fnode import FNode
from pysmt.shortcuts import Symbol, TRUE, FALSE, simplify, Times
from pysmt.typing import REAL, BOOL
from pysmt.environment import Environment, get_env

try:
    from pysdd.sdd import SddManager, SddNode
except ImportError:
    SddManager = None
    SddNode = None

from pywmi.smt_walk import CachedSmtWalker
from pywmi.errors import InstallError

from .semiring import Semiring, amc
from pywmi.engines.xsdd.vtrees.vtree import Vtree
from .literals import LiteralInfo


def product(*elements):
    result = elements[0]
    for e in elements[1:]:
        result *= e
    return result


class SddConversionWalker(CachedSmtWalker):
    def __init__(self, manager: SddManager, varnums: Dict[int, Any]):
        super().__init__()
        self.manager = manager
        self.varnums = varnums

    def walk_and(self, args):
        converted = self.walk_smt_multiple(args)
        return reduce(self.manager.conjoin, converted)

    def walk_or(self, args):
        converted = self.walk_smt_multiple(args)
        return reduce(self.manager.disjoin, converted)

    def walk_not(self, argument):
        return self.manager.negate(self.walk_smt(argument))

    def walk_ite(self, if_arg, then_arg, else_arg):
        if_arg = self.walk_smt(if_arg)
        then_arg = self.walk_smt(then_arg)
        else_arg = self.walk_smt(else_arg)
        return self.manager.disjoin(
            self.manager.conjoin(if_arg, then_arg),
            self.manager.conjoin(self.manager.negate(if_arg), else_arg),
        )

    def walk_symbol(self, name, v_type):
        assert v_type == BOOL
        return self.manager.l(self.varnums[name])

    def walk_constant(self, value, v_type):
        assert v_type == BOOL
        if value:
            return self.manager.true()
        else:
            return self.manager.false()


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
        return (
            self.reverse_abstractions[a]
            if a in self.reverse_abstractions
            else Symbol(self.lit_to_var[a], BOOL)
        )


def compile_to_sdd(formula: FNode, literals: LiteralInfo, vtree: Vtree) -> SddNode:
    if SddManager is None:
        raise InstallError(
            "The pysdd package is required for this function but is not currently installed."
        )
    varnums = literals.numbered
    pysdd_vtree = vtree.to_pysdd(varnums)
    manager = SddManager.from_vtree(pysdd_vtree)
    converter = SddConversionWalker(manager, varnums)
    return converter.walk_smt(formula)


def recover_formula(
    sdd_node: SddNode,
    literals: LiteralInfo,
    env: Environment = None,
    simplify_result=True,
) -> FNode:
    # TODO: provide a similar recover procedure in literals.py to re-insert abstractions etc
    result = amc(PySmtConversion(literals, env), sdd_node)
    return env.formula_manager.simplify(result) if simplify_result else result


# TODO: labels are not used currently. See TODO in engine.py


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
