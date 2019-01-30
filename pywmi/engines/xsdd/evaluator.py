import re
from problog.logic import term2list
from fractions import Fraction

from hal_problog.algebra.psi import WeightPSI
from hal_problog.evaluator import SemiringHAL, SemiringStaticAnalysis, WeightSA, WorldWeightTags
import psipy



pos_condition = {"'<'":psipy.less_equal, "'>'": psipy.greater_equal, "'<='": psipy.less_equal, "'>='": psipy.greater_equal, "'='": psipy.equal, "'\='": psipy.not_equal}
def construct_condition(condition):
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
    lhs = poly2expr(lhs)
    rhs = poly2expr(rhs)
    comparor = pos_condition[functor]
    ivs = comparor(lhs,rhs)
    ivs = psipy.simplify(ivs)
    return ivs

def poly2expr(poly):
    poly_numericals = re.findall("[-+]?[.]?[\d]+(?:,\d\d\d)*[.]?\d*(?:[eE][-+]?\d+)?", str(poly))
    for n in poly_numericals:
        n_rational = str(Fraction.from_float(float(n)).limit_denominator(100))
        poly = poly.replace(n, n_rational, 1)
    poly = psipy.S(str(poly))
    poly = psipy.simplify(poly)
    return poly

# def numerical_to_rational(numerical):



# def poly2expr(poly):
#     poly = sympy.sympify(poly)
#     poly = sympy.nsimplify(poly, rational=True)
#     poly = str(poly).replace("·","*").replace("**","^")
#     poly = psipy.S(poly)
#     poly = psipy.simplify(poly)
#     return poly


class SemiringWMIPSI(SemiringHAL):
    def __init__(self, neutral, abe, free_variables=None, **kwargs):
        SemiringHAL.__init__(self, neutral, abe, [], [], [], **kwargs)
        self.neutral = neutral
        self.abe = abe
        self.values_semiring = {}
        self.free_variables = free_variables or set()

    def value(self, a):
        a = a.functor
        if a.functor=="a":
            result = self.one()
        elif a.functor=="con":
            condition = a.args[0].functor
            condition = construct_condition(condition)
            variables = set(a.args[1].args)

            variables = set([(str(v),None) for v in variables])

            result = WeightPSI(condition, variables)
        else:
            raise ValueError("Illegal functor {}".format(a.functor))
        self.values_semiring[a] = result
        return result

    def result(self, evaluator, index, formula=None, normalization=False):
        a = evaluator.get_weight(index)
        return self.algebra.result(a, formula=formula)
    def normalize(self,a,z):
        return a

    def pos_value(self, a, key, index=None):
        result =  self.value(a)
        return result
    def neg_value(self, a, key, index=None):
        a = a.functor
        if a.functor=="a":
            result = self.one()
        else:
            value = self.values_semiring[a]
            if psipy.is_zero(value.expression):
                result = self.zero()
            elif psipy.is_one(value.expression):
                result = self.one()
            else:
                result = psipy.negate_condition(value.expression)
            result = WeightPSI(result, value.variables)
            result = result
        return result




    def integrate(self, weight, integrand, variables):
        integrand = psipy.simplify(integrand.expression)

        integrand = psipy.mul(weight, integrand)
        result = psipy.integrate(variables, integrand)
        return result


class SemiringWMIPSIPint(SemiringWMIPSI):
    def __init__(self, neutral, abe, **kwdargs):
        self.tags = ({},{})
        self.ww = None
        SemiringWMIPSI.__init__(self, neutral, abe, **kwdargs)



    def result(self, evaluator, index, formula=None, normalization=False):
        a = evaluator.get_weight(index)
        evaluator._computed_weights.clear() #because weights are different for each of the queries
        return self.algebra.result(a, formula=formula)

    def times(self, a, b, index=None):
        result = self.algebra.times(a,b)
        if index in self.tags[0]:
            result = self.integrate_tagged_variables(result, self.tags[0][index], self.tags[1].get(index,[]), index)
        return result
    def pos_value(self, a, key, index=None):
        result = self.value(a)
        if index in self.tags[0]:
            result = self.integrate_tagged_variables(result, self.tags[0][index], self.tags[1].get(index,[]), index)
        return result
    def neg_value(self, a, key, index=None):
        a = a.functor
        if a.functor=="a":
            return self.one()
        else:
            value = self.values_semiring[a]
            if psipy.is_zero(value.expression):
                result = self.zero()
            elif psipy.is_one(value.expression):
                result = self.one()
            else:
                result = psipy.negate_condition(value.expression)

            result = WeightPSI(result, value.variables)
            if index in self.tags[0]:
                result = self.integrate_tagged_variables(result, self.tags[0][index], self.tags[1].get(index,[]), index)
            return result




    def integrate_tagged_variables(self, weight, int_tags, weight_tags, index):
        integrand = weight.expression
        vs = set(weight.variables)
        variables = int_tags.intersection(vs)
        wvs = set(weight.weighted_variables)

        for v in weight_tags:
            if v not in wvs:
                integrand = psipy.distribute_mul(integrand, self.ww)
                wvs.add(v)
        for v in variables:
            if "poly" in wvs and (self.normalization or not self.is_free(v)):
                # print("")
                # print(index)
                # print(integrand)
                var  = v[0]
                vs.remove(v)
                # print(index)
                integrand = psipy.integrate([var], integrand)

        return WeightPSI(integrand, vs, weighted_variables=wvs.union(weight.weighted_variables))


    def is_free(self, v):
        for fv in self.free_variables:
            if fv == v[0]:
                return True
        return False

class SemiringStaticAnalysisWMI(SemiringStaticAnalysis):
    def __init__(self, neutral, abe, **kwdargs):
        SemiringStaticAnalysis.__init__(self, neutral, abe, [], [], [], **kwdargs)
        self.neutral = neutral
        self.abe = abe
        self.values_semiring = {}

    def value(self, a):
        if a.functor=="a":
            result = self.one()
        elif a.functor=="con":
            condition = a.args[0].functor
            condition = construct_condition(condition)
            variables = set([(str(v),None) for v in a.args[1].args])
            result = WeightSA(variables, variables)
        self.values_semiring[a] = result
        return result

    def times(self, a, b, index=None):
        variables = a.variables.union(b.variables)
        common_variables_children = a.variables.intersection(b.variables)
        return WeightSA(variables, common_variables_children)

    def ww_plus(self, a, b, index=None):
        result = {}
        path_lengths_a = a.variable_path_lengths
        path_lengths_b = b.variable_path_lengths

        var_a = set(path_lengths_a.keys())
        var_b = set(path_lengths_b.keys())
        for v in var_a - var_b:
            result[v] = {}
            for node_id in path_lengths_a[v]:
                result[v].update({node_id: path_lengths_a[v][node_id]+1})
        for v in var_b - var_a:
            result[v] = {}
            for node_id in path_lengths_b[v]:
                result[v].update({node_id: path_lengths_b[v][node_id]+1})
        for v in var_a & var_b:
            result[v] = {}
            node_id_a = set(path_lengths_a[v].keys())
            node_id_b = set(path_lengths_b[v].keys())
            for nid in node_id_a - node_id_b:
                result[v].update({nid: path_lengths_a[v][nid]+1})
            for nid in node_id_b - node_id_a:
                result[v].update({nid: path_lengths_b[v][nid]+1})
            for nid in node_id_a & node_id_b:
                result[v].update({nid: max(path_lengths_a[v][nid], path_lengths_b[v][nid])+1})

        if index in self.index2int_tags and "poly" not in result:
            result = {"poly":{index:0}}

        return WorldWeightTags(variable_path_lengths=result)
    def ww_times(self, a, b, index=None):
        result = {}
        path_lengths_a = a.variable_path_lengths
        path_lengths_b = b.variable_path_lengths

        var_a = set(path_lengths_a.keys())
        var_b = set(path_lengths_b.keys())
        for v in var_a - var_b:
            result[v] = {}
            for node_id in path_lengths_a[v]:
                result[v].update({node_id: path_lengths_a[v][node_id]+1})
        for v in var_b - var_a:
            result[v] = {}

            for node_id in path_lengths_b[v]:
                result[v].update({node_id: path_lengths_b[v][node_id]+1})
        for v in var_a & var_b:
            result[v] = {}
            path_sum_a = sum(path_lengths_a[v].values())
            path_sum_b = sum(path_lengths_b[v].values())

            if path_sum_a>=path_sum_b:
                for node_id in path_lengths_a[v]:
                    result[v].update({node_id: path_lengths_a[v][node_id]+1})
            else:
                for node_id in path_lengths_b[v]:

                    result[v].update({node_id: path_lengths_b[v][node_id]+1})

        if index in self.index2int_tags and "poly" not in result:
            result = {"poly":{index:0}}
        return WorldWeightTags(variable_path_lengths=result)

    def ww_value(self, a, index):
        if index in self.index2int_tags:
            variable_path_lengths = {"poly":{index:0}}
            return WorldWeightTags(variable_path_lengths=variable_path_lengths, variables=a.variables)
        else:
            return WorldWeightTags(variables = a.variables)
    def ww_negate(self,a, index):
        result = {}
        variables = a.variable_path_lengths.keys()

        if index in self.index2int_tags:
            result = {"poly":{index:0}}

        return WorldWeightTags(variable_path_lengths=result)
