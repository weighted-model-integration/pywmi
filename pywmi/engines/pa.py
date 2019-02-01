import logging
import os
import subprocess
import sys
from subprocess import TimeoutExpired
from typing import Optional, List, TYPE_CHECKING
from pysmt.environment import push_env, get_env, pop_env

from pywmi.engine import Engine

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
        self.timeout = timeout
        self.directory = directory

    def call_wmi(self, queries=None, timeout=None):
        # type: (Optional[List[FNode]], Optional[int]) -> List[Optional[float]]
        wmi_python = "/Users/samuelkolb/Documents/PhD/wmi-pa/env/bin/python"
        wmi_client = "/Users/samuelkolb/Documents/PhD/wmi-pa/experiments/client/run.py"

        filename = self.wmi_to_file(queries, self.directory)
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
        finally:
            os.remove(filename)

    def compute_volume(self, timeout=None):
        if timeout is None:
            timeout = self.timeout

        push_env()
        translated_support = get_env().formula_manager.normalize(self.support)
        translated_weight = get_env().formula_manager.normalize(self.weight)

        # noinspection PyCallingNonCallable
        solver, weights = WMI(), Weights(translated_weight)
        volume = solver.compute(
            translated_support.support & weights.labelling,
            weights,
            WMI.MODE_PA,
            domA=set(self.domain.get_bool_symbols(get_env().formula_manager)),
            domX=set(self.domain.get_real_symbols(get_env().formula_manager))
        )[0]

        pop_env()

        return volume

    def get_samples(self, n):
        raise NotImplementedError()

    def copy(self, support, weight):
        return PredicateAbstractionEngine(self.domain, support, weight)

    def __str__(self):
        return "pa" + ("" if self.timeout is None else ":t{}".format(self.timeout))
