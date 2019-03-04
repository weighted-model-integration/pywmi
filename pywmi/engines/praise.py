import logging
import os
import sys
from typing import TYPE_CHECKING

from pysmt.exceptions import NoSolverAvailableError
from pysmt.shortcuts import Solver, TRUE

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
    from wmipa import Weights, WMI, PRAiSEInference
except ImportError:
    lib_filename = os.path.join(os.path.dirname(__file__), "lib", "pa", "wmi-pa-master")
    if os.path.exists(lib_filename):
        sys.path.append(lib_filename)
        try:
            from wmipa import Weights, WMI, PRAiSEInference
        except ImportError:
            raise InstallError("Corrupted PA install")
    else:
        Weights, WMI, PRAiSEInference = None, None, None


logger = logging.getLogger(__name__)


class PraiseEngine(Engine):
    def __init__(self, domain, support, weight):
        super().__init__(domain, support, weight)
        if not pysmt_installed:
            raise InstallError("No PySMT solver is installed (not installed or not on path)")
        if WMI is None:
            raise InstallError("The wmipa library is not in your PYTHONPATH")

    def compute_volume(self, timeout=None, add_bounds=True):
        return PraiseEngine.compute_volume_pa(self.domain, self.support, self.weight)

    def compute_probabilities(self, queries, add_bounds=True):
        return [PraiseEngine.compute_volume_pa(self.domain, self.support, self.weight, query) for query in queries]

    def get_samples(self, n):
        raise NotImplementedError()

    def copy(self, domain, support, weight):
        return PraiseEngine(domain, support, weight)

    def __str__(self):
        return "praise"

    @staticmethod
    def compute_volume_pa(domain, support, weight, query=None):
        # noinspection PyCallingNonCallable
        query = query or TRUE()
        praise = PRAiSEInference(support, weight)
        return float(praise.compute_normalized_probability(query))
