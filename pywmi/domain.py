from __future__ import print_function

import json
import logging
import os
import tempfile
from typing import Optional, List, Tuple

import pysmt.shortcuts as smt
from pysmt.fnode import FNode

from .parse import smt_to_nested, nested_to_smt

logger = logging.getLogger(__name__)


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

    def domain_size(self, variable):
        return self.var_domains[variable][1] - self.var_domains[variable][0]

    def is_bool(self, variable):
        return self.var_types[variable] == smt.BOOL

    def is_real(self, variable):
        return self.var_types[variable] == smt.REAL

    def var_index_map(self):
        return {v: i for i, v in enumerate(self.variables)}

    @staticmethod
    def make(boolean_variables=None, real_variables=None, real_variable_bounds=None):
        if boolean_variables is None:
            boolean_variables = []
        else:
            boolean_variables = list(boolean_variables)
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


class TemporaryDensityFile(object):
    def __init__(self, domain, support, weight, queries=None, directory=None):
        self.domain = domain
        self.support = support
        self.weight = weight
        self.queries = queries
        self.directory = directory
        self.tmp_filename = None

    def __enter__(self):
        tmp_file = tempfile.mkstemp(suffix=".json", dir=self.directory)
        self.tmp_filename = tmp_file[1]
        logger.info("Created tmp file: {}".format(self.tmp_filename))

        # noinspection PyBroadException
        try:
            export_density(self.tmp_filename, self.domain, self.support, self.weight, self.queries)
        except Exception as e:
            print(e)
            os.remove(self.tmp_filename)

        return self.tmp_filename

    def __exit__(self, type, value, traceback):
        if os.path.exists(self.tmp_filename):
            os.remove(self.tmp_filename)


class Density(object):
    def __init__(self, domain, support, weight, queries=None):
        self.domain = domain
        self.support = support
        self.weight = weight
        self.queries = queries if queries else [smt.TRUE()]

    def export_to(self, filename):
        # type: (str) -> None
        export_density(filename, self.domain, self.support, self.weight, self.queries)

    @staticmethod
    def import_from(filename):
        return Density(*import_density(filename))


def export_density(filename, domain, support, weight, queries=None):
    # type: (str, Domain, FNode, FNode, Optional[List[FNode]]) -> None
    queries = queries if queries else [smt.TRUE()]

    flat = {
        "domain": export_domain(domain, False),
        "queries": [smt_to_nested(query) for query in queries],
        "formula": smt_to_nested(support),
        "weights": smt_to_nested(weight)
    }

    with open(filename, "w") as f:
        json.dump(flat, f)


def import_density(filename):
    # type: (str) -> Tuple[Domain, List[FNode], FNode, FNode]

    with open(filename) as f:
        flat = json.load(f)

    domain = import_domain(flat["domain"])
    queries = [nested_to_smt(query) for query in flat["queries"]]
    support = nested_to_smt(flat["formula"])
    weight = nested_to_smt(flat["weights"])

    return domain, queries, support, weight
