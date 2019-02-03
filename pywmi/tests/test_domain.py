import numpy

from pywmi import Domain


def test_projection():
    domain = Domain.make(["a", "b"], ["x", "y"], real_bounds=(0, 1))
    data = numpy.array([
        [1, 0, 0.5, 0.3],
        [0, 0, 0.2, 0.1],
    ])

    # Get boolean variables
    domain1, data1 = domain.project(["a", "b"], data)
    assert domain1.variables == ["a", "b"]
    assert (data1 == numpy.array([
        [1, 0],
        [0, 0],
    ])).all()

    # Get real variables
    domain2, data2 = domain.project(["x", "y"], data)
    assert domain2.variables == ["x", "y"]
    assert (data2 == numpy.array([
        [0.5, 0.3],
        [0.2, 0.1],
    ])).all()

    # Reorder variables
    domain3, data3 = domain.project(["x", "a"], data)
    assert domain3.variables == ["x", "a"]
    assert (data3 == numpy.array([
        [0.5, 1],
        [0.2, 0],
    ])).all()
