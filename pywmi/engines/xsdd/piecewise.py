from typing import Dict, Any

try:
    from pysdd.sdd import SddManager, SddNode
except ImportError:
    SddManager, SddNode = None, None

from pywmi.engines.algebraic_backend import AlgebraBackend


class PiecewiseXSDD(object):
    def __init__(self, sdd_dict: Dict[Any, SddNode], manager: SddManager, algebra: AlgebraBackend):
        if SddManager is None or SddNode is None:
            from pywmi.errors import InstallError
            raise InstallError("Piecewise XSDDs require the pysdd package")
        self.sdd_dict = sdd_dict
        self.manager = manager
        self.algebra = algebra

    def __add__(self, other):
        assert isinstance(other, PiecewiseXSDD)
        assert other.manager == self.manager
        assert other.algebra == self.algebra

        if len(self.sdd_dict) == 0:
            return other
        elif len(other.sdd_dict) == 0:
            return self
        else:
            new_result = dict()
            for expression1, sdd1 in self.sdd_dict.items():
                for expression2, sdd2 in other.sdd_dict.items():
                    possibilities = [
                        (expression1, self.manager.conjoin(sdd1, sdd2.negate())),
                        (expression2, self.manager.conjoin(sdd1.negate(), sdd2)),
                        (self.algebra.plus(expression1, expression2), self.manager.conjoin(sdd1, sdd2)),
                    ]
                    for e, c in possibilities:
                        if not c.is_false() or e == self.algebra.zero():
                            new_result[e] = self.manager.disjoin(new_result.get(e, self.manager.false()), c)
            return PiecewiseXSDD(new_result, self.manager, self.algebra)

    def __mul__(self, other):
        assert isinstance(other, PiecewiseXSDD)
        assert other.manager == self.manager
        assert other.algebra == self.algebra

        if len(self.sdd_dict) == 0 or len(other.sdd_dict) == 0:
            return PiecewiseXSDD(dict(), self.manager, self.algebra)
        else:
            new_result = {}
            for expression1, sdd1 in self.sdd_dict.items():
                for expression2, sdd2 in other.sdd_dict.items():
                    sdd = self.manager.conjoin(sdd1, sdd2)
                    zero = self.algebra.zero()
                    one = self.algebra.one()

                    if not sdd.is_false() and expression1 != zero and expression2 != zero:
                        if expression1 == one:
                            e = expression2
                        elif expression2 == one:
                            e = expression1
                        else:
                            e = self.algebra.times(expression1, expression2)
                        if e != zero:
                            new_result[e] = self.manager.disjoin(new_result.get(e, self.manager.false()), sdd)
            return PiecewiseXSDD(new_result, self.manager, self.algebra)

    def condition(self, condition):
        sdd_dict = {
            expression: sdd & condition for expression, sdd in self.sdd_dict.items()
        }
        return PiecewiseXSDD(sdd_dict, self.manager, self.algebra)

    def copy(self, manager: SddManager):
        copied_dict = {weight: support.copy(manager) for weight, support in self.sdd_dict.items()}
        return PiecewiseXSDD(copied_dict, manager, self.algebra)

    @staticmethod
    def ite(condition, then_expression, else_expression):
        assert isinstance(condition, SddNode)
        assert isinstance(then_expression, PiecewiseXSDD)
        assert isinstance(else_expression, PiecewiseXSDD)

        return then_expression.condition(condition) + else_expression.condition(condition.negate())

    @staticmethod
    def symbol(name, manager: SddManager, algebra: AlgebraBackend):
        return PiecewiseXSDD({algebra.symbol(name): manager.true()}, manager, algebra)

    @staticmethod
    def real(float_constant, manager: SddManager, algebra: AlgebraBackend, convert=True):
        if convert:
            float_constant = algebra.real(float_constant)
        return PiecewiseXSDD({float_constant: manager.true()}, manager, algebra)

    def __neg__(self):
        sdd_dict = {
            self.algebra.negate(expression): sdd for expression, sdd in self.sdd_dict.items()
        }
        return PiecewiseXSDD(sdd_dict, self.manager, self.algebra)


