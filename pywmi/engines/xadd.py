import logging
import os
import re
import subprocess
import sys
from typing import Optional, List

from pysmt.fnode import FNode
from pysmt.shortcuts import Real, TRUE

from pywmi.domain import TemporaryDensityFile
from pywmi.engine import Engine

logger = logging.getLogger(__name__)


class XaddEngine(Engine):
    pattern = re.compile(r"\n(-?\d+\.\d+E?\d*) (-?\d+\.\d+E?\d*)\n")
    path = os.path.join(os.path.dirname(__file__), "xadd.jar")

    def __init__(self, domain, support, weight, mode=None, timeout=None):
        super().__init__(domain, support, weight)
        self.mode = mode
        self.timeout = timeout

    def call_wmi(self, queries=None, timeout=None):
        # type: (Optional[List[FNode]], Optional[int]) -> Optional[List[Optional[float]]]

        timeout = timeout if timeout else self.timeout

        with self.temp_file(queries) as f:
            try:
                cmd_args = ["java", "-jar", XaddEngine.path, "inference", f] + ([self.mode] if self.mode else [])
                logger.info("> {}".format(" ".join(cmd_args)))
                output = subprocess.check_output(cmd_args, timeout=timeout).decode(sys.stdout.encoding)
                results = [(float(match[0]) if queries is not None else float(match[1]))
                           for match in XaddEngine.pattern.findall(output)]
                return results
            except subprocess.CalledProcessError as e:
                logger.warning(e.output)
            except subprocess.TimeoutExpired:
                logger.warning("Timeout")
            except ValueError:
                logger.warning(output)
                raise
        return None

    def compute_volume(self, timeout=None):
        if timeout is None:
            timeout = self.timeout
        result = self.call_wmi(timeout=timeout)
        if result is None or len(result) == 0:
            return None
        else:
            return result[0]

    def copy(self, support, weight):
        return XaddEngine(self.domain, support, weight, self.mode, self.timeout)

    def get_samples(self, n):
        raise NotImplementedError()

    def normalize(self, new_support, paths=True):
        # type: (FNode, str, bool) -> bool

        with self.temp_file() as f:
            with TemporaryDensityFile(self.domain, new_support, Real(1.0)) as f2:
                with TemporaryDensityFile(self.domain, TRUE(), Real(1.0)) as f3:
                    try:
                        cmd_args = ["java", "-jar", XaddEngine.path, "normalize", f, f2, "-p" if paths else "-t", f3]
                        logger.info("> {}".format(" ".join(cmd_args)))
                        output = subprocess.check_output(cmd_args, timeout=self.timeout).decode(sys.stdout.encoding)
                        return import_xadd_mspn(f3)[2]
                    except subprocess.CalledProcessError as e:
                        logger.warning(e.output)
                        raise
                    except subprocess.TimeoutExpired:
                        logger.warning("Timeout")
                    except ValueError:
                        logger.warning(output)
                        raise
        return None

    def __str__(self):
        result = "xadd:m{}".format(self.mode)
        if self.timeout is not None:
            result += ":t{}".format(self.timeout)
        return result
