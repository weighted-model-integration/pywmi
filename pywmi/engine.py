import logging
from typing import List, TypeVar, Dict

from pysmt.fnode import FNode
from pysmt.shortcuts import simplify
from pysmt.typing import BOOL

from pywmi import Domain, Density
from pywmi.temp import TemporaryFile

logger = logging.getLogger(__name__)

# noinspection PyTypeChecker
T = TypeVar('T', bound='Engine')


class Engine:
    def __init__(self, domain=None, support=None, weight=None, exact=True):
        # type: (Domain, FNode, FNode, bool) -> None
        self.exact = exact
        self.domain = domain
        self.support = support
        self.weight = weight

    def compute_volume(self, add_bounds=True):
        # type: (bool) -> float
        raise NotImplementedError()

    def compute_probabilities(self, queries, add_bounds=True):
        # type: (List[FNode], bool) -> List[float]
        volume = self.compute_volume(add_bounds=add_bounds)
        return [self.with_constraint(query).compute_volume(add_bounds=add_bounds) / volume if volume > 0 else None
                for query in queries]

    def compute_probability(self, query, add_bounds=True):
        # type: (FNode, bool) -> float
        return self.compute_probabilities([query], add_bounds=add_bounds)[0]

    def with_evidence(self, substitutions):
        # type: (T, Dict[FNode, FNode]) -> T
        variables_to_remove = set()
        for k, v in substitutions.items():
            assert k.is_symbol()
            assert k.symbol_type() == BOOL
            assert v.is_constant()
            variables_to_remove.add(k.symbol_name())
        variables = [v for v in self.domain.variables if v not in variables_to_remove]
        domain = Domain(variables, {v: self.domain.var_types[v] for v in variables}, self.domain.var_domains)
        support = self.support.substitute(substitutions)
        weight = simplify(self.weight.substitute(substitutions))
        return self.copy(domain, support, weight)

    def with_constraint(self, constraint):
        # type: (T, FNode) -> T
        return self.copy_with(support=self.support & constraint)

    def copy_with(self, domain=None, support=None, weight=None):
        # type: (T, Domain, FNode, FNode) -> T
        domain = domain or self.domain
        support = support or self.support
        weight = weight or self.weight
        return self.copy(domain, support, weight)

    def copy(self, domain, support, weight):
        # type: (T, Domain, FNode, FNode) -> T
        raise NotImplementedError()

    def temp_file(self, queries=None, directory=None):
        density = Density(self.domain, self.support, self.weight, queries)
        return TemporaryFile(directory=directory, callback=density.to_file)
