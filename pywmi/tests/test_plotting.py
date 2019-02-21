import matplotlib as mpl
from PIL import Image
from pysmt.shortcuts import Real, Ite

from pywmi import Domain, nested_to_smt, Density
from pywmi.plot import plot_data, plot_formula, plot_density
from pywmi.sample import uniform
from pywmi.smt_check import evaluate
from pywmi.temp import TemporaryFile


def _test_plot_data():
    domain = Domain.make(["a"], ["x", "y"], [(0, 1), (0, 1)])
    a, x, y = domain.get_symbols(["a", "x", "y"])
    formula = a | (~a & (x <= y))
    data = uniform(domain, 100)
    labels = evaluate(domain, formula, data)
    mpl.use('Agg')
    plot_data(None, domain, (data, labels))
    assert True


def test_plot_xor():
    domain = Domain.make(["a", "b"], ["x", "y"], [(0, 1), (0, 1)])
    a, b, x, y = domain.get_symbols()
    formula = ((x * -2.539851974031258e-15 + y * 3.539312736703863e-15 <= Real(0.0)) | ~a | ~b) \
        & (a | b) \
        & (Real(0.0) < x * -2.539851974031258e-15 + y * 3.539312736703863e-15)

    with TemporaryFile(suffix=".png") as filename:
        plot_formula(filename, domain, formula)
        image = Image.open(filename)
        assert image.getpixel((900, 900)) == image.getpixel((300, 300))


def test_plot_boolean_or():
    nested_string = "(| (var bool a) (var bool b))"
    domain = Domain.make(["a", "b"], ["x", "y"], [(0, 1), (0, 1)])
    formula = nested_to_smt(nested_string)
    with TemporaryFile(suffix=".png") as filename:
        plot_formula(filename, domain, formula)
        image = Image.open(filename)
        assert image.getpixel((900, 900)) == image.getpixel((300, 900))


def test_plot_density():
    domain = Domain.make([], ["x", "y"], [(-2.5, 2.7), (0, 1)])
    x, y = domain.get_symbols()
    support = (y <= x * 0.7 + 0.5) & (y >= x * 1.3 - 1)
    weight = Ite(x <= y, Ite(x < 0, -x, x), 3 - y)
    plot_density(Density(domain, support, weight))