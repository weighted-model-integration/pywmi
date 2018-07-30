from random import random

import numpy

from pywmi import test
from engine import Engine


def sample(bounds, n):
    samples = numpy.random.random((n, len(bounds)))
    for d in range(len(bounds)):
        a, b = bounds[d]
        samples[:, d] = a[0] + samples[:, d] * (b[0] - a[0])
    return samples


def weighted_sample(weights, values, n):
    # https://stackoverflow.com/a/2151885/253387
    total = float(sum(weights))
    i = 0
    w, v = weights[0], values[0]
    while n:
        x = total * (1 - random.random() ** (1.0 / n))
        total -= x
        while x > w:
            x -= w
            i += 1
            w, v = weights[i], values[i]
        w -= x
        yield v
        n -= 1


class RejectionEngine(Engine):
    def __init__(self, domain, support, weight, extra_sample_ratio):
        super().__init__(domain, support, weight)
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
        samples = sample(bounds, n * self.extra_sample_ratio)
        labels = test(self.domain, self.support, None, samples)

        if self.weight is not None:
            sample_weights = test(self.domain, self.weight, numpy.array([]), samples[labels])
            return numpy.array(list(weighted_sample(sample_weights, samples, n)))
        else:
            raise NotImplementedError()

    def copy(self, support, weight):
        return RejectionEngine(self.domain, support, weight, self.extra_sample_ratio)

