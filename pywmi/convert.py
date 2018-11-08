import json
import os
from typing import Tuple, List

from pysmt.fnode import FNode

from .domain import import_density, import_domain
from pywmi import Domain, nested_to_smt
from pysmt import shortcuts as smt


def import_xadd_mspn(filename):
    # type: (str) -> Tuple[Domain, FNode, FNode, List[FNode]]
    name = os.path.basename(filename)
    parts = name.split("_")
    real_vars = int(parts[1])
    bool_vars = int(parts[2])

    domain = Domain.make(["A_{}".format(i) for i in range(bool_vars)],
                         {"x_{}".format(i): [0, 1] for i in range(real_vars)})

    support = smt.TRUE()
    with open(filename) as f:
        weight = nested_to_smt(f.readlines()[0])
    queries = [smt.TRUE()]

    return domain, support, weight, queries


def import_wmi_mspn(filename):
    # type: (str) -> Tuple[Domain, FNode, FNode, List[FNode]]
    q_file, s_file, w_file = ("{}.{}".format(filename, ext) for ext in ["query", "support", "weight"])
    queries = [smt.TRUE()] if not os.path.exists(q_file) else [smt.read_smtlib(q_file)]
    support = smt.read_smtlib(s_file)
    if os.path.exists(w_file):
        weights = smt.read_smtlib(w_file)
    else:
        weights = smt.Real(1)
    name = os.path.basename(filename)
    parts = name.split("_")
    real_vars = int(parts[1])
    bool_vars = int(parts[2])

    domain = Domain.make(["A_{}".format(i) for i in range(bool_vars)],
                         {"x_{}".format(i): [0, 1] for i in range(real_vars)})

    return domain, support, weights, queries


def import_smt_synthetic(filename):
    # type: (str) -> Tuple[Domain, FNode, FNode, List[FNode]]

    with open(filename) as f:
        flat = json.load(f)

    domain = import_domain(flat["synthetic_problem"]["problem"]["domain"])
    queries = [smt.TRUE()]
    support = nested_to_smt(flat["synthetic_problem"]["problem"]["theory"]) & domain.get_bounds()
    weights = smt.Real(1)

    return domain, support, weights, queries


def import_wmi_generate_tree(filename):
    # type: (str) -> Tuple[Domain, FNode, FNode, List[FNode]]
    queries = [smt.read_smtlib(filename + "_0.query")]
    support = smt.read_smtlib(filename + "_0.support")
    weights = smt.read_smtlib(filename + "_0.weights")
    variables = queries[0].get_free_variables() | support.get_free_variables() | weights.get_free_variables()
    domain = Domain.make(real_variables={v.symbol_name(): [0, 1] for v in variables if v.symbol_type() == smt.REAL},
                         boolean_variables=[v.symbol_name() for v in variables if v.symbol_type() == smt.BOOL])
    return domain, support, weights, queries


def import_wmi_generate_100(filename):
    # type: (str) -> Tuple[Domain, FNode, FNode, List[FNode]]
    queries = [smt.read_smtlib(filename + "_0.query")]
    support = smt.read_smtlib(filename + "_0.support")
    weights = smt.read_smtlib(filename + "_0.weights")
    variables = queries[0].get_free_variables() | support.get_free_variables() | weights.get_free_variables()
    domain = Domain.make(real_variables={v.symbol_name(): [-100, 100] for v in variables if v.symbol_type() == smt.REAL},
                         boolean_variables=[v.symbol_name() for v in variables if v.symbol_type() == smt.BOOL])
    return domain, support, weights, queries


def import_wrap(fn):
    domain, queries, support, weight = import_density(fn)
    return domain, support, weight, queries


class Import(object):
    _dialects = {
        None: import_wrap,
        "xadd_mspn": import_xadd_mspn,
        "wmi_mspn": import_wmi_mspn,
        "smt_synthetic": import_smt_synthetic,
        "wmi_generate_tree": import_wmi_generate_tree,
        "wmi_generate_100": import_wmi_generate_100,
    }

    dialects = sorted(k for k in _dialects.keys() if k is not None)

    @staticmethod
    def import_density(filename, dialect=None):
        # type: (str, str) -> Tuple[Domain, FNode, FNode, List[FNode]]
        if dialect in Import._dialects:
            return Import._dialects[dialect](filename)
        raise ValueError("Invalid dialect: {}".format(dialect))
