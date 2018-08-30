import json
import os
import subprocess
import logging
import sys
import tempfile
from typing import Optional, List, TYPE_CHECKING

from pysmt.shortcuts import TRUE

from pywmi.engine import Engine
from pywmi import export_domain, smt_to_nested

if TYPE_CHECKING:
    from pysmt.fnode import FNode

logger = logging.getLogger(__name__)


class PredicateAbstraction(Engine):
    def __init__(self, domain, support, weight, directory=None, timeout=None):
        super().__init__(domain, support, weight)
        self.timeout = timeout
        self.directory = directory

    def call_wmi(self, queries=None, timeout=None):
        # type: (Optional[List[FNode]], Optional[int]) -> List[float]
        wmi_python = "/Users/samuelkolb/Documents/PhD/wmi-pa/env/bin/python"
        wmi_client = "/Users/samuelkolb/Documents/PhD/wmi-pa/experiments/client/run.py"

        if queries is None:
            queries = [TRUE()]

        flat = {
            "domain": export_domain(self.domain, False),
            "queries": [smt_to_nested(query) for query in queries],
            "formula": smt_to_nested(self.support),
            "weights": smt_to_nested(self.weight)
        }

        (fd, filename) = tempfile.mkstemp(suffix=".json", dir=self.directory)
        try:
            logger.info("Created tmp file: {}".format(filename))
            with open(filename, "w") as f:
                json.dump(flat, f)
            logger.info("> {} {} -f {} -v".format(wmi_python, wmi_client, filename))
            output = subprocess.check_output([wmi_python, wmi_client, "-f", filename, "-v"]).decode(sys.stdout.encoding)
            return [float(line.split(": ")[1]) for line in str(output).split("\n")[:-1]]
        except ValueError:
            output = str(subprocess.check_output(["cat", filename]))
            logger.warning("File content:\n{}".format(output))
            raise
        finally:
            os.remove(filename)

    def compute_volume(self, timeout=None):
        if timeout is None:
            timeout = self.timeout

        return self.call_wmi(timeout=timeout)[0]

    def get_samples(self, n):
        raise NotImplementedError()

    def copy(self, support, weight):
        return PredicateAbstraction(self.domain, support, weight)

    def __str__(self):
        return "PA" + ("" if self.timeout is None else ":t{}".format(self.timeout))
