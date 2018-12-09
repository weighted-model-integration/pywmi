import matplotlib as mpl

from pywmi import Domain
from pywmi.plot import plot_data
from pywmi.sample import uniform
from pywmi.smt_check import evaluate


def test_plot_data():
    domain = Domain.make(["a"], ["x", "y"], [(0, 1), (0, 1)])
    a, x, y = domain.get_symbols(["a", "x", "y"])
    formula = a | (~a & (x <= y))
    data = uniform(domain, 100)
    labels = evaluate(domain, formula, data)
    mpl.use('Agg')
    plot_data(None, domain, (data, labels))
    assert True
