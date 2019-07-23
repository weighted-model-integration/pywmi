from scipy.optimize import minimize, LinearConstraint, Bounds
import numpy as np


def objective(x):
    x0, x1, x2, x3 = x[0], x[1], x[2], x[3]
    return x0*x1*x3*1.0 + x0*x1*(-1.0) + x0*x1*x3*(-1.0) + x0*x1*1.0 + x0*x3*(-1.0)\
        + x0*1.0 + x0*x3*1.0 + x0*(-1.0) + x1*x3*(-1.0) + x1*1.0 + x1*x3*1.0 + x1*(-1.0)\
        + x3*1.0 + (-1.0) + x3*(-1.0) + 1.0 + x0*x3


if __name__ == "__main__":
    initial_value = np.array([1., 1., 1., 1.])
    a = [[-1.0, 0, 0, 0], [0, -1.0, 0, 0], [0, 0, -1.0, 0], [0, 0, 0, -1.0], [0, 0, -1.0, 0], [0, 0, 0, 1.0], [0, -1.0, 0, 0], [-1.0, 0, 0, 0], [0, 0, 1.0, 0], [0, 1.0, 0, 0], [1.0, 0, 0, 0], [-2.0, 0, 0, 0], [0, 0, 0, -1.0], [0, -2.0, 0, 0], [0, 0, -2.0, 0], [0, 0, 0, -2.0]]
    b = [1.0, 1.0, 1.0, 1.0, 0, 1.0, 0, 0, 1.0, 1.0, 1.0, -1.0, 0, -1.0, -1.0, -1.0]
    lin_constraints = LinearConstraint(a, np.full(len(b), -np.inf), b)
    res = minimize(objective, initial_value, method='trust-constr', bounds=Bounds(np.full(4, -2), np.full(4, 2)),
                   constraints=lin_constraints)
    print(res.fun)
