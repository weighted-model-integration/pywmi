import logging
from typing import List, Tuple, Optional

import numpy as np
from pysmt.fnode import FNode

from pywmi import Domain
from .domain import TemporaryDensityFile

logger = logging.getLogger(__name__)


class Engine(object):
    def __init__(self, domain, support, weight, add_bounds=True, exact=True):
        # type: (Domain, FNode, FNode, bool, bool) -> None
        self.domain = domain
        self.support = (domain.get_bounds() & support) if add_bounds else support
        self.weight = weight
        self.exact = exact

    def compute_volume(self):
        # type: () -> float
        raise NotImplementedError()

    def compute_probabilities(self, queries):
        # type: (List[FNode]) -> List[float]
        volume = self.compute_volume()
        return [self.copy(self.support & query, self.weight).compute_volume() / float(volume) for query in queries]

    def compute_probability(self, query):
        # type: (FNode) -> float
        return self.compute_probabilities([query])[0]

    def get_samples(self, n):
        # type: (int) -> np.ndarray
        raise NotImplementedError()

    def copy(self, support, weight):
        # type: (FNode, FNode) -> Engine
        raise NotImplementedError()

    def bound_tuples(self):
        # type: () -> Tuple[Tuple[Tuple[float, bool], Tuple[float, bool]], ...]
        return tuple(
            ((self.domain.var_domains[var][0], True), (self.domain.var_domains[var][1], True))
            for var in self.domain.real_vars
        )

    def bound_volume(self, bounds=None):
        # type: (Optional[Tuple[Tuple[Tuple[float, bool], Tuple[float, bool]], ...]]) -> Optional[float]

        if bounds is None:
            bounds = self.bound_tuples()

        if bounds is None or len(bounds) == 0:
            return None

        volume = 1
        for lb_bound, ub_bound in bounds:
            volume *= ub_bound[0] - lb_bound[0]
        return volume

    def temp_file(self, queries=None, directory=None):
        return TemporaryDensityFile(self.domain, self.support, self.weight, queries, directory)
