import numpy
import numpy as np

from pywmi import Domain, evaluate


class SamplingError(RuntimeError):
    def __init__(self, msg=""):
        self.msg = msg


def uniform(domain: Domain, sample_count: int):
    samples = np.random.random((sample_count, len(domain.variables)))
    for i, var in enumerate(domain.variables):
        if domain.is_bool(var):
            samples[:, i] = samples[:, i] < 0.5
        else:
            lb, ub = domain.var_domains[var]
            samples[:, i] = lb + samples[:, i] * (ub - lb)

    return samples


def weighted_sample(weights, values, n):
    # https://stackoverflow.com/a/2151885/253387
    total = float(sum(weights))
    i = 0
    w, v = weights[0], values[0]
    while n:
        x = total * (1 - numpy.random.random() ** (1.0 / n))
        total -= x
        while x > w:
            x -= w
            i += 1
            w, v = weights[i], values[i]
        w -= x
        yield v
        n -= 1


def positive(required_sample_count, domain, support, weight=None, sample_pool_size=None, sample_count=None,
             max_samples=None):
    sample_pool_size = sample_pool_size or (required_sample_count if weight is None else required_sample_count * 10)
    sample_count = sample_count or sample_pool_size * 2
    max_samples = max_samples or sample_count * 10
    samples = uniform(domain, sample_count)
    labels = evaluate(domain, support, samples)
    pos_samples = samples[labels]

    while pos_samples.shape[0] < sample_pool_size:
        if sample_count >= max_samples:
            raise SamplingError("Max sample count {} exceeded (could not find pool of size {})"
                                .format(max_samples, sample_pool_size))

        pos_ratio = pos_samples.shape[0] / sample_count
        estimated_count = (sample_pool_size - pos_samples.shape[0]) / max(pos_ratio, 0.001)
        new_sample_count = min(int(estimated_count * 1.1), max_samples - sample_count)
        new_samples = uniform(domain, new_sample_count)
        new_labels = evaluate(domain, support, new_samples)
        new_pos_samples = new_samples[new_labels]
        if pos_samples.shape[0] > 0:
            print(pos_samples, new_pos_samples)
            pos_samples = numpy.concatenate((pos_samples, new_pos_samples), axis=0)
        else:
            pos_samples = new_pos_samples
        sample_count = sample_count + new_sample_count

    pos_ratio = pos_samples.shape[0] / sample_count

    if pos_samples.shape[0] > sample_pool_size:
        pos_samples = pos_samples[:sample_pool_size]

    if weight is not None:
        sample_weights = evaluate(domain, weight, pos_samples)
        return numpy.array(list(weighted_sample(sample_weights, pos_samples, required_sample_count))), pos_ratio
    else:
        return pos_samples, pos_ratio
