from typing import List, TYPE_CHECKING, Tuple, Optional


if TYPE_CHECKING:
    from pysmt.fnode import FNode
    import numpy as np
    from pywmi import Domain


class Engine(object):
    def __init__(self, domain, support, weight, exact=True):
        self.domain = domain  # type: Domain
        self.support = support  # type: FNode
        self.weight = weight  # type: FNode
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
