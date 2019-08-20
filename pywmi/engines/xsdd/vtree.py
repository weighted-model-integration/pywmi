from pysdd.sdd import Vtree, SddManager
from typing import Dict

from pysmt.fnode import FNode

from pywmi import Domain
from pywmi.smt_print import pretty_print


def get_new_manager(domain: Domain, abstractions: Dict[FNode, int], var_to_lit: Dict[str, int], strategy: str):
    def key(_t):
        if len(_t[0].get_free_variables()) == 0:
            return len(domain.real_vars), -1
        return len(domain.real_vars)-len(_t[0].get_free_variables()), min(domain.real_vars.index(str(v)) for v in _t[0].get_free_variables())

    var_count = max(list(abstractions.values()) + list(var_to_lit.values()))
    inequality_order = [t[1] for t in sorted(abstractions.items(), key=key)]
    print(*[pretty_print(t[0]) for t in sorted(abstractions.items(), key=key)], sep="\n")
    bool_order = [t[1] for t in sorted(var_to_lit.items(), key=lambda vl: domain.bool_vars.index(vl[0]))]

    tree = Vtree(var_count, bool_order + inequality_order, strategy)
    # noinspection PyArgumentList
    return SddManager.from_vtree(tree)
