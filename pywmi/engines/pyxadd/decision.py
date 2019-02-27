from typing import Tuple, List, Type, Optional, Dict

from pysmt.fnode import FNode
from pysmt.shortcuts import simplify, TRUE, FALSE
from pysmt.typing import BOOL

from pywmi import smt_to_nested
from pywmi.export import Exportable
from pywmi.smt_math import LinearInequality
from pywmi.smt_print import pretty_print


def to_canonical(inequality: LinearInequality) -> LinearInequality:
    keys = sorted(inequality.inequality_dict.keys())
    factor = abs(inequality.inequality_dict[keys[0]])
    return LinearInequality({k: v / factor for k, v in inequality.inequality_dict.items()})


class Decision(Exportable):
    def __init__(self, test: FNode, variables: Optional[List[FNode]] = None, is_canonical=False,
                 inequality: Optional[LinearInequality] = None):
        self.test = test
        self._variables = variables
        self.is_canonical = is_canonical
        self._inequality = inequality
        self._is_bool = None

    @property
    def variables(self):
        if self._variables is None:
            self._variables = self.test.get_free_variables()
        return self._variables

    @property
    def inequality(self):
        if self._inequality is None:
            self._inequality = LinearInequality.from_smt(self.test)
        return self._inequality

    def get_valid_branches(self) -> List[bool]:
        """
        Returns the valid branches (True, False or both)
        """
        simplified = self.test
        if simplified not in [TRUE(), FALSE()]:
            if self.is_bool():
                simplified = simplify(simplified)
            else:
                simplified = simplify(self.inequality.to_smt())
        if simplified == TRUE():
            return [True]
        elif simplified == FALSE():
            return [False]
        else:
            return [True, False]

    def is_bool(self):
        if self._is_bool is None:
            test = self.test
            self._is_bool = (test.is_symbol() and test.symbol_type() == BOOL) or\
                            (test.is_not() and test.args()[0].is_symbol())
        return self._is_bool

    def to_canonical(self, child_true: int, child_false: int) -> Tuple['Decision', int, int]:
        if self.is_canonical:
            return self, child_true, child_false
        if self.is_bool():
            if self.test.is_symbol():
                self.is_canonical = True
                return self, child_true, child_false
            else:
                decision = Decision(simplify(~self.test), self._variables, True)
                print(decision)
                assert decision.test.is_symbol()
                return decision, child_false, child_true

        inequality = LinearInequality.from_smt(self.test)
        keys = sorted(inequality.inequality_dict.keys())
        if len(keys) == 0:
            print("IN", inequality)
        factor = abs(inequality.inequality_dict[keys[0]])
        result = {k: v / factor for k, v in inequality.inequality_dict.items()}
        if result[keys[0]] < 0:
            result = {k: -v for k, v in result.items()}
            child_true, child_false = child_false, child_true

        canonical_inequality = LinearInequality(result)
        decision = Decision(canonical_inequality.to_smt(), self._variables, True, canonical_inequality)

        # canonical_inequality = LinearInequality.from_smt(self.test).normalize()
        # if canonical_inequality.b() < 0:
        #     canonical_inequality = LinearInequality({k: -v for k, v, in canonical_inequality.inequality_dict.items()})
        #     child_true, child_false = child_false, child_true
        # decision = Decision(canonical_inequality.to_smt(), self._variables, True, canonical_inequality)
        return decision, child_true, child_false

    def evaluate(self, assignment):
        raise NotImplementedError()

    def rename(self, translation: Dict[FNode, FNode]) -> 'Decision':
        return Decision(self.test.substitute(translation))

    def __repr__(self):
        return "Decision({})".format(smt_to_nested(self.test))

    def __str__(self):
        return pretty_print(self.test)

    def __hash__(self):
        return hash(self.test)

    def __eq__(self, other):
        return isinstance(other, Decision) and self.test == other.test

    def get_state(self) -> dict:
        return {"test": smt_to_nested(self.test)}

    @classmethod
    def from_state(cls: Type['Decision'], state: dict) -> 'Decision':
        return cls(state["test"])

    def update_bounds(self, var, lb, ub, test=True):
        raise NotImplementedError()
