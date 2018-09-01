import json
import os
import subprocess
import logging
import sys
import tempfile
from subprocess import TimeoutExpired
from typing import Optional, List, TYPE_CHECKING

from pysmt.shortcuts import TRUE

from pywmi.engine import Engine
from pywmi import export_domain, smt_to_nested

if TYPE_CHECKING:
    from pysmt.fnode import FNode

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

        return self.call_wmi(timeout=timeout)[0]

    def get_samples(self, n):
        raise NotImplementedError()

    def copy(self, support, weight):
        return PredicateAbstractionEngine(self.domain, support, weight)

    def __str__(self):
        return "pa" + ("" if self.timeout is None else ":t{}".format(self.timeout))
