from problog.logic import term2list

from hal_problog.algebra.psi import WeightPSI
from hal_problog.evaluator import SemiringHAL
import psipy




class SemiringWMIPSI(SemiringHAL):
    pos_condition = {"'<'":psipy.less_equal, "'>'": psipy.greater_equal, "'<='": psipy.less_equal, "'>='": psipy.greater_equal, "'='": psipy.equal, "'\='": psipy.not_equal}

    def __init__(self, neutral, abe, **kwdargs):
        SemiringHAL.__init__(self, neutral, abe, [], [], [], **kwdargs)
        self.neutral = neutral
        self.abe = abe
        self.values_semiring = {}

    def value(self, a):
        a = a.functor
        if a.functor=="a":
            result = self.one()
        elif a.functor=="con":
            condition = a.args[0].functor
            condition = self.construct_condition(condition)
            variables = set(a.args[1].args)

            result = WeightPSI(condition, variables)
        self.values_semiring[a] = result
        return result

    def result(self, a, formula=None, normalization=False):
        return a
    def normalize(self,a,z):
        return a

    def pos_value(self, a, key, index=None):
        return self.value(a)
    def neg_value(self, a, key, index=None):
        a = a.functor
        if a.functor=="a":
            return self.one()
        else:
            value = self.values_semiring[a]
            result = psipy.negate_condition(value.expression)
            result = WeightPSI(result, value.variables)
            return result

    def construct_condition(self, condition):
        if ">=" in condition:
            functor = ">="
        elif "<=" in condition:
            functor = "<="
        elif ">" in condition:
            functor = ">"
        elif "<" in condition:
            functor = "<"
        lhs, rhs = condition.split(functor)
        functor = "'{}'".format(functor)
        lhs = self.poly2expr(lhs)
        rhs = self.poly2expr(rhs)
        comparor = self.pos_condition[functor]
        ivs = comparor(lhs,rhs)
        ivs = psipy.simplify(ivs)
        return ivs

    def poly2expr(self, poly):
        # poly = poly.replace(".0","") #this his hacky should be replaced with actucal symbolic manipulation!
        poly = psipy.S(str(poly))
        poly = psipy.simplify(poly)
        return poly


    def integrate(self, weight, integrand, variables):
        # print(weight)
        # print(integrand)
        integrand = psipy.simplify(integrand.expression)

        integrand = psipy.mul(weight, integrand)
        result = psipy.integrate(variables, integrand)
        return result
