import logging
import os
import sys
from argparse import ArgumentParser
from typing import TYPE_CHECKING

from pysmt.exceptions import NoSolverAvailableError
from pysmt.shortcuts import Solver, Bool

from pywmi import Density
from pywmi.engine import Engine
from pywmi.errors import InstallError

if TYPE_CHECKING:
    pass

try:
    with Solver() as solver:
        pysmt_installed = True
except NoSolverAvailableError:
    pysmt_installed = False

try:
    from mpwmi import MPWMI

except ImportError:
    MPWMI = None


logger = logging.getLogger(__name__)


class MPWMIEngine(Engine):
    def __init__(self, domain, support, weight, cache=False):
        super().__init__(domain, support, weight)
        if not pysmt_installed:
            raise InstallError("No PySMT solver is installed (not installed or not on path)")
        if MPWMI is None:
            raise InstallError("The pympwmi library is not in your PYTHONPATH")

        self.cache = cache

    def compute_probabilities(self, queries, add_bounds=True):
        if add_bounds:
            return self.with_constraint(self.domain.get_bounds()).compute_probabilities(queries, add_bounds=False)

        Z, vol_Q = MPWMIEngine.compute_volumes(self.support, self.weight, queries=queries, cache=self.cache)
        return [float(q / Z) for q in vol_Q]

    def compute_volume(self, add_bounds=True):
        if add_bounds:
            return self.with_constraint(self.domain.get_bounds()).compute_volume(add_bounds=False)

        return float(MPWMIEngine.compute_volumes(self.support, self.weight, queries=[], cache=self.cache)[0])

    def get_samples(self, n):
        raise NotImplementedError()

    def copy(self, domain, support, weight):
        return MPWMIEngine(domain, support, weight, cache=self.cache)

    def __str__(self):
        return "mpwmi" + (" w/cache" if self.cache else "")

    @staticmethod
    def compute_volumes(support, weight, queries=None, cache=False):
        solver = MPWMI(support, weight)
        return solver.compute_volumes(queries=queries, cache=cache)


if __name__ == "__main__":
    if MPWMI is None:
        raise InstallError("The pympwmi library is not in your PYTHONPATH")

    parser = ArgumentParser()
    parser.add_argument("filename", type=str)
    args = parser.parse_args()

    density = Density.from_file(args.filename)
    Z, vol_Q = MPWMIEngine.compute_volume_mpwmi(density.domain, density.support, density.weight)
    print(Z)
    print(vol_Q)
