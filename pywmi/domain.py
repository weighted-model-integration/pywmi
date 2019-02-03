from __future__ import print_function

import logging
import numpy as np
from typing import Optional, List, Tuple
from pywmi.export import Exportable

import pysmt.shortcuts as smt
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager

from .parse import smt_to_nested, nested_to_smt

logger = logging.getLogger(__name__)


class Domain(Exportable):
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

    def sym(self, variable, formula_manager=None):
        return self.get_symbol(variable, formula_manager)

    def get_symbols(self, variables=None, formula_manager=None):
        # type: (Optional[List[str]], Optional[FormulaManager]) -> List[FNode]
        return [self.get_symbol(v, formula_manager) for v in (variables if variables is not None else self.variables)]

    def get_real_symbols(self, formula_manager=None):
        # type: (Optional[FormulaManager]) -> List[FNode]
        return self.get_symbols(self.real_vars, formula_manager)

    def get_bool_symbols(self, formula_manager=None):
        # type: (Optional[FormulaManager]) -> List[FNode]
        return self.get_symbols(self.bool_vars, formula_manager)

    def get_bounds(self, formula_manager=None):
        fm = smt if formula_manager is None else formula_manager
        bounds = []
        for v, (lb, ub) in self.var_domains.items():
            symbol = self.get_symbol(v, formula_manager)
            if lb is not None:
                bounds.append(symbol >= lb)
            if ub is not None:
                bounds.append(symbol <= ub)
        return fm.And(*bounds)

    def domain_size(self, variable):
        return self.var_domains[variable][1] - self.var_domains[variable][0]

    def is_bool(self, variable):
        return self.var_types[variable] == smt.BOOL

    def is_real(self, variable):
        return self.var_types[variable] == smt.REAL

    def var_index_map(self):
        return {v: i for i, v in enumerate(self.variables)}

    def change_bounds(self, new_var_bounds):
        if not isinstance(new_var_bounds, dict):
            new_var_bounds = {v: new_var_bounds for v in self.real_vars}
        return Domain(self.variables, self.var_types, new_var_bounds)

    def get_bounding_box_volume(self):
        # type: () -> float

        if len(self.real_vars) == 0:
            return 0

        volume = 1
        for lb, ub in self.var_domains.values():
            if lb is None or ub is None:
                return float("inf")
            volume *= ub - lb
        return volume

    def get_volume(self):
        # type: () -> float
        return self.get_bounding_box_volume() * 2**len(self.bool_vars)

    @staticmethod
    def make(boolean_variables=None, real_variables=None, real_variable_bounds=None, real_bounds=None):
        if boolean_variables is None:
            boolean_variables = []
        else:
            boolean_variables = list(boolean_variables)
        if real_variable_bounds and real_bounds:
            raise ValueError("Cannot specify both real_variable_bounds and real_bounds")
        if real_bounds:
            real_variable_bounds = [real_bounds for _ in real_variables]
        if real_variables is None and real_variable_bounds is None:
            real_names = []
            bounds = dict()
        elif real_variables is not None and real_variable_bounds is None:
            real_names = list(real_variables.keys())
            bounds = real_variables
        else:
            real_names = real_variables
            if isinstance(real_variable_bounds, dict):
                raise ValueError("real_variable_bounds should be list or iterable")
            bounds = dict(zip(real_variables, real_variable_bounds))
        types = {v: smt.BOOL for v in boolean_variables}
        types.update({v: smt.REAL for v in bounds})
        return Domain(boolean_variables + real_names, types, bounds)

    @staticmethod
    def build(*args, **kwargs):
        return Domain.make(args, kwargs)

    def __str__(self):
        return "({})".format(", ".join(
            ("{}[{}, {}]".format(v, *self.var_domains[v]) if self.var_types[v] is smt.REAL else v)
            for v in self.variables))

    def get_state(self):
        def export_type(_t):
            if _t == smt.BOOL:
                return "bool"
            elif _t == smt.REAL:
                return "real"
            else:
                raise RuntimeError("Unknown type {}".format(_t))

        return {
            "variables": self.variables,
            "var_types": {v: export_type(t) for v, t in self.var_types.items()},
            "var_domains": self.var_domains,
        }

    @classmethod
    def from_state(cls, state):
        def import_type(_t):
            if _t == "bool":
                return smt.BOOL
            elif _t == "real":
                return smt.REAL
            else:
                raise RuntimeError("Unknown type {}".format(_t))

        variables = [str(v) for v in state["variables"]]
        var_types = {str(v): import_type(str(t)) for v, t in state["var_types"].items()}
        var_domains = {str(v): t for v, t in state["var_domains"].items()}
        return cls(variables, var_types, var_domains)

    def project(self, variables_to_keep, data):
        # type: (List[str], np.ndarray) -> Tuple[Domain, np.ndarray]
        var_types = {v: self.var_types[v] for v in variables_to_keep}
        var_domains = {v: self.var_domains[v] for v in variables_to_keep if self.is_real(v)}
        new_domain = Domain(variables_to_keep, var_types, var_domains)
        variable_indices = [self.variables.index(v) for v in variables_to_keep]
        new_data = data[:, variable_indices]
        return new_domain, new_data

    def project_real(self, data):
        return self.project(self.real_vars, data)

    def project_bool(self, data):
        return self.project(self.bool_vars, data)


class Density(Exportable):
    def __init__(self, domain, support, weight, queries=None):
        self.domain = domain
        self.support = support
        self.weight = weight
        self.queries = queries if queries is not None else [smt.TRUE()]

    def get_state(self):
        return {
            "domain": self.domain.get_state(),
            "queries": [smt_to_nested(query) for query in self.queries],
            "formula": smt_to_nested(self.support),
            "weights": smt_to_nested(self.weight)
        }

    @classmethod
    def from_state(cls, state: dict):
        return cls(
            Domain.from_state(state["domain"]),
            nested_to_smt(state["formula"]),
            nested_to_smt(state["weights"]),
            [nested_to_smt(query) for query in state["queries"]],
        )
