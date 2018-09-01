import json
import logging
import os
import tempfile
from typing import List, TYPE_CHECKING, Tuple, Optional

from pysmt.shortcuts import TRUE

from .domain import TemporaryDensityFile
from pywmi import Domain, export_domain, smt_to_nested
from pysmt.fnode import FNode
import numpy as np

logger = logging.getLogger(__name__)


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

    def temp_file(self, queries=None, directory=None):
        return TemporaryDensityFile(self.domain, self.support, self.weight, queries, directory)

    def wmi_to_file(self, queries=None, dir=None):
        # type: (Optional[List[FNode]], Optional[str]) -> str
        if queries is None:
            queries = [TRUE()]

        flat = {
            "domain": export_domain(self.domain, False),
            "queries": [smt_to_nested(query) for query in queries],
            "formula": smt_to_nested(self.support),
            "weights": smt_to_nested(self.weight)
        }

        fd, filename = tempfile.mkstemp(suffix=".json", dir=dir)

        try:
            logger.info("Created tmp file: {}".format(filename))
            with open(filename, "w") as f:
                json.dump(flat, f)
        except Exception:
            os.remove(filename)

        return filename
