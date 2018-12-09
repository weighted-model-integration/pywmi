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

    def pos_value(self, a, index=None):
        return self.value(a)
    def neg_value(self, a, inde=None):
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
        lhs = self.poly2psi(lhs)
        rhs = self.poly2psi(rhs)
        comparor = self.pos_condition[functor]
        ivs = comparor(lhs,rhs)
        ivs = psipy.simplify(ivs)
        return ivs
    def poly2psi(self, poly):
        # poly = poly.replace(".0","") #this his hacky should be replaced with actucal symbolic manipulation!
        poly = psipy.S(str(poly))
        poly = psipy.simplify(poly)
        return poly












    #
    # def weight(self, result, dde=None, **kwdargs):
    #     # if self.draw_diagram:
    #     self.make_diagram(dde)
    #
    #     wmi_query = psipy.S("0")
    #     wmi_evidence = psipy.S("0")
    #
    #     e_integrals = 0
    #     q_integrals = 0
    #     q_integrals_cached = 0
    #
    #
    #     query_weights = {}
    #     evidence_weights = {}
    #
    #
    #     for key, weight in result.items():
    #         if key.functor=="q" and weight:
    #
    #             q_key = key.args[0]
    #             query_weights[q_key] = weight
    #         elif key.functor=="e" and weight:
    #
    #             e_key = key.args[0]
    #             evidence_weights[e_key] = weight
    #             w = self.weight_literal2weight_function[e_key]
    #
    #             w = psipy.simplify(psipy.S(str(w).replace(".0","")))
    #             self.world_weights[e_key] = w
    #             w= psipy.terms(w)
    #             self.world_weights_list[e_key] = w
    #
    #
    #
    #     for e in evidence_weights:
    #         integrant_iverson_e = evidence_weights[e].weight
    #         integral_e = self.integrate(integrant_iverson_e, self.world_weights[e], self.i_var)
    #         wmi_evidence = psipy.add(wmi_evidence,integral_e)
    #         wmi_evidence = psipy.simplify(wmi_evidence)
    #
    #         e_integrals += 1
    #
    #
    #         if e in query_weights:
    #             integrant_iverson_q = query_weights[e].weight
    #
    #             if integrant_iverson_q==integrant_iverson_e:
    #                 integral_q = integral_e
    #                 wmi_query = psipy.add(wmi_query,integral_q)
    #                 wmi_query = psipy.simplify(wmi_query)
    #                 q_integrals_cached += 1
    #             else:
    #                 integral_q = self.integrate(integrant_iverson_q, self.world_weights[e], self.i_var)
    #
    #                 wmi_query = psipy.add(wmi_query,integral_q)
    #                 wmi_query = psipy.simplify(wmi_query)
    #
    #                 q_integrals += 1
    #
    #     probability = psipy.div(wmi_query, wmi_evidence)
    #     probability = psipy.simplify(probability)
    #     return OrderedDict([("WMI Query",wmi_query), ("WMI Evidence",wmi_evidence), \
    #     ("Probability",probability), ("evidence integrations",e_integrals),\
    #      ("query integrations",q_integrals), ("cached query integrations",q_integrals_cached)])
