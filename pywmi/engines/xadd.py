import logging
import os
import re
import subprocess
import sys
from typing import Optional, List

from pysmt.fnode import FNode
from pysmt.shortcuts import Real, TRUE

from pywmi import Density
from pywmi.errors import InstallError
from pywmi.smt_math import LinearInequality, Polynomial
from pywmi.temp import TemporaryFile
from .integration_backend import IntegrationBackend
from pywmi.engine import Engine
import pysmt.shortcuts as smt

logger = logging.getLogger(__name__)


class XaddEngine(Engine):
    pattern = re.compile(r"\n(-?\d+\.\d+E?-?\d*) (-?\d+\.\d+E?-?\d*)\n")

    def __init__(self, domain, support, weight, mode=None, timeout=None):
        super().__init__(domain, support, weight)
        if not os.path.exists(XaddEngine.path()):
            raise InstallError("The XADD engine requires the XADD library JAR file which is currently not installed.")
        self.mode = mode
        self.timeout = timeout

    @staticmethod
    def path():
        return os.environ.get("XADD_PATH", os.path.join(os.path.dirname(__file__), "xadd.jar"))

    def call_wmi(self, queries=None, timeout=None):
        # type: (Optional[List[FNode]], Optional[int]) -> Optional[List[Optional[float]]]

        if not os.path.exists(XaddEngine.path()):
            raise RuntimeError("The XADD engine requires the XADD library JAR file which is currently not installed.")

        timeout = timeout if timeout else self.timeout

        with self.temp_file(queries) as f:
            try:
                cmd_args = ["java", "-jar", XaddEngine.path(), "inference", f] + ([self.mode] if self.mode else [])
                logger.info("> {}".format(" ".join(cmd_args)))
                output = subprocess.check_output(cmd_args, timeout=timeout).decode(sys.stdout.encoding)  # type: str
                # print(output.replace("Academic license - for non-commercial use only\n", ""))
                results = [(float(match[0]) if queries is not None else float(match[1]))
                           for match in XaddEngine.pattern.findall(output)]
                return results
            except subprocess.CalledProcessError as e:
                logger.warning(e.output.decode(sys.stdout.encoding)
                               .replace("Academic license - for non-commercial use only\n", ""))
            except subprocess.TimeoutExpired:
                logger.warning("Timeout")
            except ValueError:
                logger.warning(output.replace("Academic license - for non-commercial use only\n", ""))
                raise
        return None

    def compute_volume(self, timeout=None, add_bounds=True):
        if add_bounds:
            return self.with_constraint(self.domain.get_bounds()).compute_volume(timeout, False)
        if timeout is None:
            timeout = self.timeout
        result = self.call_wmi(timeout=timeout)
        if result is None or len(result) == 0:
            return None
        else:
            return result[0]

    def copy(self, domain, support, weight):
        return XaddEngine(domain, support, weight, self.mode, self.timeout)

    def get_samples(self, n):
        raise NotImplementedError()

    def normalize(self, new_support, conjoin_old_support=True, paths=True):
        # type: (FNode, bool, bool) -> Optional[FNode]

        if not os.path.exists(XaddEngine.path()):
            raise RuntimeError("The XADD engine requires the XADD library JAR file which is currently not installed.")

        if conjoin_old_support:
            new_support = self.support & new_support

        with self.temp_file() as f:
            with TemporaryFile() as f2:
                Density(self.domain, new_support, Real(1.0)).to_file(f2)
                with TemporaryFile() as f3:
                    Density(self.domain, TRUE(), Real(1.0)).to_file(f3)

                    try:
                        cmd_args = ["java", "-jar", XaddEngine.path(), "normalize", f, f2, "-p" if paths else "-t", f3]
                        logger.info("> {}".format(" ".join(cmd_args)))
                        output = subprocess.check_output(cmd_args, timeout=self.timeout).decode(sys.stdout.encoding)
                        # print(output.replace("Academic license - for non-commercial use only\n", ""))
                        return XaddEngine.import_normalized(f3)
                    except subprocess.CalledProcessError as e:
                        logger.warning(e.output)
                        raise
                    except subprocess.TimeoutExpired:
                        logger.warning("Timeout")
                    except ValueError:
                        logger.warning(output)
                        raise
        return None

    @staticmethod
    def import_normalized(filename):
        from pywmi import nested_to_smt
        with open(filename) as f:
            return nested_to_smt(f.readlines()[0])

    def __str__(self):
        result = "xadd:m{}".format(self.mode)
        if self.timeout is not None:
            result += ":t{}".format(self.timeout)
        return result


class XaddIntegrator(IntegrationBackend):
    def __init__(self, mode=None):
        super().__init__(True)
        self.mode = mode

    def partially_integrate(self, domain, convex_bounds: List[LinearInequality], polynomial: Polynomial,
                            variables: List[str]):
        raise NotImplementedError()

    def integrate(self, domain, convex_bounds: List[LinearInequality], polynomial: Polynomial):
        formula = smt.And(*[i.to_smt() for i in convex_bounds])
        engine = XaddEngine(domain, formula, polynomial.to_smt(), self.mode)
        return engine.compute_volume()

    def __str__(self):
        return "xadd_int.{}".format(self.mode) if self.mode else "xadd_int"
