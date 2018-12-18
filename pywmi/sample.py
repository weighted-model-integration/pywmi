import numpy as np

from pywmi import Domain


def uniform(domain: Domain, sample_count: int):
    samples = np.random.random((sample_count, len(domain.variables)))
    for i, var in enumerate(domain.variables):
        if domain.is_bool(var):
            samples[:, i] = samples[:, i] < 0.5
        else:
            lb, ub = domain.var_domains[var]
            samples[:, i] = lb + samples[:, i] * (ub - lb)

    return samples
