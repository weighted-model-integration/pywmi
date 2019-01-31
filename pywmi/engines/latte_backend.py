import logging
import os
import re
import shutil
import tempfile
from fractions import Fraction
from subprocess import check_output, DEVNULL
from typing import List

from pywmi.smt_math import LinearInequality, Polynomial
from .integration_backend import IntegrationBackend

logger = logging.getLogger(__name__)


class TemporaryFile(object):
    def __init__(self, directory=None, suffix=None):
        self.directory = directory
        self.tmp_filename = None
        self.suffix = suffix

    def __enter__(self):
        tmp_file = tempfile.mkstemp(suffix=self.suffix, dir=self.directory)
        self.tmp_filename = tmp_file[1]
        logger.info("Created tmp file: {}".format(self.tmp_filename))
        return self.tmp_filename

    def __exit__(self, t, value, traceback):
        if os.path.exists(self.tmp_filename):
            os.remove(self.tmp_filename)


class LatteIntegrator(IntegrationBackend):
    pattern = re.compile(r".*Answer:\s+(-?\d+)/(\d+).*")

    def __init__(self):
        super().__init__(True)
        if not shutil.which("integrate"):
            from pywmi.errors import InstallError
            raise InstallError("Latte (integrate) is not installed")
        self.algorithm = "--cone-decompose"

    def partially_integrate(self, domain, convex_bounds: List[LinearInequality], polynomial: Polynomial, variables: List[str]):
        raise NotImplementedError()

    @staticmethod
    def key_to_exponents(domain, key: tuple):
        return [key.count(v) for v in domain.real_vars]

    def integrate(self, domain, convex_bounds: List[LinearInequality], polynomial: Polynomial):
        # TODO Use power of linear forms?
        b_geq_a = []
        for bound in convex_bounds:
            integer_bound = bound.scale_to_integer()
            b_geq_a.append([integer_bound.b()] + [-integer_bound.a(v) for v in domain.real_vars])

        monomials = [(Fraction(value).limit_denominator(), self.key_to_exponents(domain, key))
                     for key, value in polynomial.poly_dict.items()]

        with TemporaryFile(suffix=".hrep.latte") as bounds_file:
            with TemporaryFile(suffix=".poly.latte") as poly_file:
                with open(bounds_file, "w") as bounds_ref:
                    print("{} {}".format(len(b_geq_a), len(domain.real_vars) + 1), file=bounds_ref)
                    print(*[" ".join(map(str, e)) for e in b_geq_a], sep="\n", file=bounds_ref)

                with open(poly_file, "w") as poly_ref:
                    print("[{}]".format(",".join("[{},[{}]]".format(m[0], ",".join(map(str, m[1])))
                                                 for m in monomials)), file=poly_ref)

                command = "integrate --valuation=integrate {} --monomials={} {}"\
                    .format(self.algorithm, poly_file, bounds_file)
                output = check_output(command, shell=True, stderr=DEVNULL).decode()
                match = re.search(self.pattern, output)
                if not match:
                    raise RuntimeError("Could not find answer in Latte output: {output}".format(output=output))
                return float(Fraction(int(match.group(1)), int(match.group(2))))

    def __str__(self):
        return "latte_int"
