import logging
from argparse import ArgumentParser
from typing import TYPE_CHECKING


from pysmt.shortcuts import Bool

from pywmi import Density
from pywmi.engine import Engine
from pywmi.errors import InstallError

if TYPE_CHECKING:
    pass


try:
    from wmipa import WMI
except ImportError:
    WMI = None


logger = logging.getLogger(__name__)


class PredicateAbstractionEngine(Engine):
    def __init__(self, domain, support, weight, directory=None, timeout=None):
        if WMI is None:
            raise InstallError()

        super().__init__(domain, support, weight)
        self.timeout = timeout
        self.directory = directory

    def compute_volume(self, add_bounds=True):
        if add_bounds:
            return self.with_constraint(self.domain.get_bounds()).compute_volume(
                add_bounds=False
            )
        return PredicateAbstractionEngine.compute_volume_pa(
            self.domain, self.support, self.weight
        )

    def get_samples(self, n):
        raise NotImplementedError()

    def copy(self, domain, support, weight):
        return PredicateAbstractionEngine(
            domain, support, weight, directory=self.directory, timeout=self.timeout
        )

    def __str__(self):
        return "pa" + ("" if self.timeout is None else ":t{}".format(self.timeout))

    @staticmethod
    def compute_volume_pa(domain, support, weight, convex_backend=None):
        # noinspection PyCallingNonCallable
        solver = WMI(support, weight, convex_backend=convex_backend)
        return solver.computeWMI(
            Bool(True),
            mode=WMI.MODE_PA,
            domA=set(domain.get_bool_symbols()),
            domX=set(domain.get_real_symbols()),
        )[0]


if __name__ == "__main__":

    parser = ArgumentParser()
    parser.add_argument("filename", type=str)
    args = parser.parse_args()

    density = Density.from_file(args.filename)
    print(
        PredicateAbstractionEngine.compute_volume_pa(
            density.domain, density.support, density.weight
        )
    )
