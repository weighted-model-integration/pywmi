import numpy

from builtins import range
from pywmi import test
from pywmi.engine import Engine


def sample(bounds, n_boolean_vars, n):
    boolean_samples = numpy.random.random((n, n_boolean_vars)) < 0.5

    real_samples = numpy.random.random((n, len(bounds)))
    for d in range(len(bounds)):
        a, b = bounds[d]
        real_samples[:, d] = a[0] + real_samples[:, d] * (b[0] - a[0])

    return boolean_samples, real_samples


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


class RejectionEngine(Engine):
    def __init__(self, domain, support, weight, extra_sample_ratio, seed):
        Engine.__init__(self, domain, support, weight)
        if seed is not None:
            numpy.random.seed(seed)
        self.seed = seed
        self.extra_sample_ratio = extra_sample_ratio

    def compute_volume(self):
        # bounds = self.bound_tuples()
        # bound_volume = self.bound_volume(bounds)
        # samples = sample(bounds, n * self.extra_sample_ratio)
        # labels = test(self.domain, self.support, None, samples)
        #
        # if self.weight is not None:
        #     sample_weights = test(self.domain, self.weight, numpy.array([]), samples[labels])
        #     rejection_volume = sum(sample_weights) / len(labels) * bound_volume
        # else:
        #     rejection_volume = sum(labels) / len(labels) * bound_volume
        # return rejection_volume
        raise NotImplementedError()

    def get_samples(self, n):
        bounds = self.bound_tuples()
        real_samples, boolean_samples = sample(bounds,
                                               len(self.domain.bool_vars),
                                               n * self.extra_sample_ratio)

        samples = numpy.concatenate((real_samples, boolean_samples), axis=1)
        
        labels = test(self.domain, self.support, boolean_samples, real_samples)

        if self.weight is not None:
            sample_weights = test(self.domain, self.weight, numpy.array([]), samples[labels])
            return numpy.array(list(weighted_sample(sample_weights, samples, n)))
        else:
            raise NotImplementedError()

    def copy(self, support, weight):
        return RejectionEngine(self.domain, support, weight, self.extra_sample_ratio, self.seed)

