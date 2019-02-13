from pysmt.fnode import FNode
from pysmt.shortcuts import Real
from pysmt.typing import REAL

from pywmi.smt_walk import SmtIdentityWalker


class PositiveCoefficientsWalker(SmtIdentityWalker):
    def walk_constant(self, value, v_type):
        if v_type == REAL:
            return Real(abs(value))
        else:
            return SmtIdentityWalker.walk_constant(self, value, v_type)


def make_coefficients_positive(formula: FNode) -> FNode:
    return PositiveCoefficientsWalker().walk_smt(formula)
