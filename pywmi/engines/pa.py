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
    Weights, WMI = None, None


logger = logging.getLogger(__name__)


class PredicateAbstractionEngine(Engine):
    def __init__(self, domain, support, weight, directory=None, timeout=None):
        super().__init__(domain, support, weight)
        if WMI is None:
            raise InstallError("The wmipa library is not in your PYTHONPATH")
        self.timeout = timeout
        self.directory = directory

    def call_wmi(self, queries=None, timeout=None):
        # type: (Optional[List[FNode]], Optional[int]) -> List[Optional[float]]
        wmi_python = "/Users/samuelkolb/Documents/PhD/wmi-pa/env/bin/python"
        wmi_client = "/Users/samuelkolb/Documents/PhD/wmi-pa/experiments/client/run.py"

        with self.temp_file(queries) as filename:
            try:
                args = [wmi_python, wmi_client, "-f", filename, "-v"]
                logger.info("> {}".format(" ".join(args)))
                output = subprocess.check_output(args, timeout=timeout).decode(sys.stdout.encoding)
                return [float(line.split(": ")[1]) for line in str(output).split("\n")[:-1]]
            except TimeoutExpired:
                return [None for _ in range(1 if queries is None else len(queries))]
            except ValueError:
                output = str(subprocess.check_output(["cat", filename]))
                logger.warning("File content:\n{}".format(output))
                raise

    def compute_volume(self, timeout=None):
        print(self.call_wmi())

        timeout = timeout or self.timeout
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

    def get_samples(self, n):
        raise NotImplementedError()

    def copy(self, support, weight):
        return PredicateAbstractionEngine(self.domain, support, weight)

    def __str__(self):
        return "pa" + ("" if self.timeout is None else ":t{}".format(self.timeout))


if __name__ == "__main__":
    if WMI is None:
        raise InstallError("The wmipa library is not in your PYTHONPATH")

    parser = ArgumentParser()
    parser.add_argument("filename", type=str)
    args = parser.parse_args()

    density = Density.from_file(args.filename)
    print(density.domain, pretty_print(density.support), pretty_print(density.weight))

    # noinspection PyCallingNonCallable
    solver, weights = WMI(), Weights(density.weight)
    volume = solver.compute(
        density.support & weights.labelling,
        weights,
        WMI.MODE_PA,
        domA=set(density.domain.get_bool_symbols()),
        domX=set(density.domain.get_real_symbols())
    )[0]
    print(volume)

    weights_d = Weights(density.weight)
    support_d = density.support & weights_d.labelling
    wmisolver = WMI()
    print(wmisolver.compute(support_d, weights_d, WMI.MODE_PA)[0])

    # print()
    # print(density.domain, pretty_print(density.support), pretty_print(density.weight), end="")

