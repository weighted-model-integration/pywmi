from __future__ import print_function

import json

import pysmt.shortcuts as smt


class Domain(object):
    def __init__(self, variables, var_types, var_domains):
        self.variables = variables
        self.var_types = var_types
        self.var_domains = var_domains

    @property
    def bool_vars(self):
        return [v for v in self.variables if self.var_types[v] == smt.BOOL]

    @property
    def real_vars(self):
        return [v for v in self.variables if self.var_types[v] == smt.REAL]

    def get_symbol(self, variable, formula_manager=None):
        if formula_manager is None:
            formula_manager = smt
        return formula_manager.Symbol(variable, self.var_types[variable])

    def get_bounds(self, formula_manager=None):
        fm = smt if formula_manager is None else formula_manager
        sym = fm.Symbol
        bounds = [(sym(v, smt.REAL) >= b[0]) & (sym(v, smt.REAL) <= b[1]) for v, b in self.var_domains.items()]
        return fm.And(*bounds)

    @staticmethod
    def make(boolean_variables=None, real_variable_bounds=None):
        if boolean_variables is None:
            boolean_variables = []
        if real_variable_bounds is None:
            real_variable_bounds = dict()
        types = {v: smt.BOOL for v in boolean_variables}
        types.update({v: smt.REAL for v in real_variable_bounds})
        return Domain(boolean_variables + list(real_variable_bounds.keys()), types, real_variable_bounds)

    def __str__(self):
        return "({})".format(", ".join(
            ("{}[{}, {}]".format(v, *self.var_domains[v]) if self.var_types[v] is smt.REAL else v)
            for v in self.variables))


def export_domain(domain, to_str=True):
    def export_type(_t):
        if _t == smt.BOOL:
            return "bool"
        elif _t == smt.REAL:
            return "real"
        else:
            raise RuntimeError("Unknown type {}".format(_t))

    flat = {
        "variables": domain.variables,
        "var_types": {v: export_type(t) for v, t in domain.var_types.items()},
        "var_domains": domain.var_domains,
    }
    return json.dumps(flat) if to_str else flat


def import_domain(flat):
    def import_type(_t):
        if _t == "bool":
            return smt.BOOL
        elif _t == "real":
            return smt.REAL
        else:
            raise RuntimeError("Unknown type {}".format(_t))

    variables = [str(v) for v in flat["variables"]]
    var_types = {str(v): import_type(str(t)) for v, t in flat["var_types"].items()}
    var_domains = {str(v): t for v, t in flat["var_domains"].items()}
    return Domain(variables, var_types, var_domains)
