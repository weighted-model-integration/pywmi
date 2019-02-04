import pytest
from pysmt.shortcuts import Real, TRUE

from pywmi.errors import InstallError
from pywmi import Domain, XaddEngine

try:
    # noinspection PyTypeChecker
    XaddEngine(None, None, None)
    xadd_installed = True
except InstallError:
    xadd_installed = False


@pytest.mark.skipif(not xadd_installed, reason="XADD engine is not installed")
def test_minus():
    domain = Domain.make([], ["x"], [(0, 1)])
    x, = domain.get_symbols()
    support = TRUE()
    weight = Real(1) - x
    engine = XaddEngine(domain, support, weight)
    assert engine.compute_volume() is not None
