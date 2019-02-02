import logging
import os
import subprocess
import sys
from argparse import ArgumentParser
from subprocess import TimeoutExpired
from typing import Optional, List, TYPE_CHECKING

from autodora.parallel import run_command
from pysmt.environment import push_env, get_env, pop_env

from pywmi.errors import InstallError
from pywmi import Density
from pywmi.engine import Engine
from pywmi.smt_print import pretty_print

if TYPE_CHECKING:
    from pysmt.fnode import FNode

try:
    from wmipa import Weights, WMI
except ImportError:
    lib_filename = os.path.join(os.path.dirname(__file__), "lib", "pa", "wmi-pa-master")
    if os.path.exists(lib_filename):
        sys.path.append(lib_filename)
        try:
            from wmipa import Weights, WMI
        except ImportError:
            raise RuntimeError("Corrupted PA install")
    else:
        Weights, WMI = None, None


logger = logging.getLogger(__name__)


class PredicateAbstractionEngine(Engine):
    def __init__(self, domain, support, weight, add_bounds=True, directory=None, timeout=None):
        super().__init__(domain, support, weight, add_bounds=add_bounds)
        if WMI is None:
            raise InstallError("The wmipa library is not in your PYTHONPATH")
        self.timeout = timeout
        self.directory = directory

    def compute_volume(self, timeout=None):
        timeout = timeout or self.timeout
        if timeout:
            with self.temp_file() as filename:
                print(pretty_print(self.support))
                print(pretty_print(self.weight))
                out, err = run_command("python {} {}".format(__file__, filename), timeout=timeout)
                print("\nOUT ---")
                print(out)
                print("---")
            try:
                return float(out.split("\n")[-1])
            except TypeError:
                raise RuntimeError("Could not convert:{}\nError output:\n{}".format(out, err))
        else:
            return PredicateAbstractionEngine.compute_volume_pa(self.domain, self.support, self.weight)

    def get_samples(self, n):
        raise NotImplementedError()

    def copy(self, support, weight):
        return PredicateAbstractionEngine(self.domain, support, weight)

    def __str__(self):
        return "pa" + ("" if self.timeout is None else ":t{}".format(self.timeout))

    @staticmethod
    def compute_volume_pa(domain, support, weight):
        # noinspection PyCallingNonCallable
        solver, weights = WMI(), Weights(weight)
        return solver.compute(
            support & weights.labelling,
            weights,
            WMI.MODE_PA,
            domA=set(domain.get_bool_symbols()),
            domX=set(domain.get_real_symbols())
        )[0]


if __name__ == "__main__":
    if WMI is None:
        raise InstallError("The wmipa library is not in your PYTHONPATH")

    parser = ArgumentParser()
    parser.add_argument("filename", type=str)
    args = parser.parse_args()

    density = Density.from_file(args.filename)
    print(PredicateAbstractionEngine.compute_volume_pa(density.domain, density.support, density.weight))
