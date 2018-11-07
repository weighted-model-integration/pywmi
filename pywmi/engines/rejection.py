import numpy

from builtins import range
from pywmi import evaluate
from pywmi.engine import Engine
from pywmi.exceptions import SamplingException


def sample(n_boolean_vars, bounds, n):
    samples = numpy.random.random((n, n_boolean_vars + len(bounds)))
    samples[:, 0:n_boolean_vars] = samples[:, 0:n_boolean_vars] < 0.5

    for d in range(len(bounds)):
        a, b = bounds[d]
        samples[:, n_boolean_vars + d] = a[0] + samples[:, n_boolean_vars + d] * (b[0] - a[0])

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


class RejectionEngine(Engine):
    def __init__(self, domain, support, weight, sample_count, seed=None):
        Engine.__init__(self, domain, support, weight, exact=False)
        if seed is not None:
            numpy.random.seed(seed)
        self.seed = seed
        self.sample_count = sample_count

    def compute_volume(self, sample_count=None):
        sample_count = sample_count if sample_count is not None else self.sample_count
        bounds = self.bound_tuples()
        samples = sample(len(self.domain.bool_vars), bounds, sample_count)
        labels = evaluate(self.domain, self.support, samples)
        pos_samples = samples[labels]
        bound_volume = self.bound_volume(bounds) * 2**len(self.domain.bool_vars)
        approx_volume = bound_volume * sum(labels) / len(labels)

        if self.weight is not None:
            sample_weights = evaluate(self.domain, self.weight, pos_samples)
            rejection_volume = sum(sample_weights) / len(pos_samples) * approx_volume
        else:
            rejection_volume = approx_volume

        return rejection_volume

    def get_samples(self, n, extra_sample_ratio=None, weighted=True):
        sample_count = n * extra_sample_ratio if extra_sample_ratio is not None else self.sample_count
        bounds = self.bound_tuples()
        samples = sample(len(self.domain.bool_vars), bounds, sample_count)
        labels = evaluate(self.domain, self.support, samples)
        pos_samples = samples[labels]

        if len(pos_samples) < n:
            msg = "Sampled points {}, needed {}"
            raise SamplingException(msg.format(len(pos_samples), n))

        pos_ratio = sum(labels) / len(labels)

        if weighted and self.weight is not None:
            sample_weights = evaluate(self.domain, self.weight, pos_samples)
            return numpy.array(list(weighted_sample(sample_weights, pos_samples, n))), pos_ratio
        else:
            return numpy.array(list(pos_samples)[:n]), pos_ratio

    def copy(self, support, weight):
        return RejectionEngine(self.domain, support, weight, self.sample_count, self.seed)

    def __str__(self):
        return "rej" + (":n{}".format(self.sample_count))
