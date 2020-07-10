import logging
import os
import sys
from argparse import ArgumentParser
from typing import TYPE_CHECKING

from autodora.parallel import run_command
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
    from pympwmi import MPWMI
except ImportError:
    lib_filename = os.path.join(os.path.dirname(__file__), "lib", "mpwmi", "pympwmi-master")
    if os.path.exists(lib_filename):
        sys.path.append(lib_filename)
        try:
            from pympwmi import MPWMI
        except ImportError:
            raise RuntimeError("Corrupted pympwmi install")
    else:
        WMI = None


logger = logging.getLogger(__name__)


class MPWMIEngine(Engine):
    def __init__(self, domain, support, weight, timeout=None, cache=False):
        super().__init__(domain, support, weight)
        if not pysmt_installed:
            raise InstallError("No PySMT solver is installed (not installed or not on path)")
        if MPWMI is None:
            raise InstallError("The pympwmi library is not in your PYTHONPATH")
        self.timeout = timeout
        self.cache = cache


    def compute_probabilities(self, queries, timeout=None):
        timeout = timeout or self.timeout
        if timeout:
            with self.temp_file(queries=queries) as filename:
                out, err = run_command("python {} {}".format(__file__, filename), timeout=timeout)
            try:
                res = out.split("\n")[-2:]
                Z, vol_Q = float(res[0]), eval(res[1])
            except TypeError:
                raise RuntimeError("Could not convert:{}\nError output:\n{}".format(out, err))
        else:
            Z, vol_Q = MPWMIEngine.compute_volumes(self.support, self.weight, queries, self.cache)
        return [float(q / Z) for q in vol_Q]

    def compute_volume(self, timeout=None, add_bounds=True):
        if add_bounds:
            return self.with_constraint(self.domain.get_bounds()).compute_volume(timeout=timeout, add_bounds=False)

        timeout = timeout or self.timeout
        if timeout:
            with self.temp_file() as filename:
                out, err = run_command("python {} {}".format(__file__, filename), timeout=timeout)
            try:
                return float(out.split("\n")[-2])
            except TypeError:
                raise RuntimeError("Could not convert:{}\nError output:\n{}".format(out, err))
        else:
            return float(MPWMIEngine.compute_volumes(self.support, self.weight, [], self.cache)[0])

    def get_samples(self, n):
        raise NotImplementedError()

    def copy(self, domain, support, weight):
        return MPWMIEngine(domain, support, weight, timeout=self.timeout, cache=self.cache)

    def __str__(self):
        return "mpwmi" + ("" if self.timeout is None else ":t{}".format(self.timeout))

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
