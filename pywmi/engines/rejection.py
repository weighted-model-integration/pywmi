from functools import reduce
from typing import List

import numpy

from builtins import range

import scipy.optimize

from pywmi.sample import uniform
from .xsdd.smt_to_sdd import product
from pywmi.smt_math import LinearInequality, Polynomial
from .integration_backend import IntegrationBackend
from pywmi import evaluate, Domain
from pywmi.engine import Engine
from pywmi.exceptions import SamplingException
import pysmt.shortcuts as smt


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
            try:
                rejection_volume = sum(sample_weights) / len(pos_samples) * approx_volume
            except ZeroDivisionError:
                rejection_volume = 0.0
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


class RejectionIntegrator(IntegrationBackend):
    def __init__(self, sample_count, bounding_box=False):
        super().__init__(False)
        self.sample_count = sample_count
        self.bounding_box = bounding_box

    def partially_integrate(self, domain, convex_bounds: List[LinearInequality], polynomial: Polynomial,
                            variables: List[str]):
        raise NotImplementedError()

    def integrate(self, domain, convex_bounds: List[LinearInequality], polynomial: Polynomial):
        formula = smt.And(*[i.to_smt() for i in convex_bounds])

        if self.bounding_box > 0:
            if self.bounding_box == 1:
                a_matrix = numpy.zeros((len(convex_bounds), len(domain.real_vars)))
                b_matrix = numpy.zeros((len(convex_bounds),))
                for i, bound in enumerate(convex_bounds):
                    for j in range(len(domain.real_vars)):
                        a_matrix[i, j] = bound.a(domain.real_vars[j])
                    b_matrix[i] = bound.b()

                lb_ub_bounds = {}
                c = numpy.zeros((len(domain.real_vars),))
                for j in range(len(domain.real_vars)):
                    c[j] = 1
                    lb = scipy.optimize.linprog(c, a_matrix, b_matrix).x[j]
                    ub = scipy.optimize.linprog(-c, a_matrix, b_matrix).x[j]
                    c[j] = 0
                    lb_ub_bounds[domain.real_vars[j]] = (lb, ub)
            elif self.bounding_box == 2:
                samples = uniform(domain, self.sample_count)
                labels = evaluate(domain, formula, samples)
                samples = samples[labels == 1]
                print()
                print(min(samples[:, -1]))
                try:
                    samples.sort(axis=0)
                    std = abs(samples[0:-1, :] - samples[1:, :]).std(axis=0)
                    lbs = samples[0, :] - std
                    ubs = samples[-1, :] + std
                except ValueError:
                    return 0

                lb_ub_bounds = {domain.variables[j]: (lbs[j], ubs[j]) for j in range(len(domain.variables))}
            else:
                raise ValueError(f"Illegal bounding box value {self.bounding_box}")
            domain = Domain(domain.variables, domain.var_types, lb_ub_bounds)

        engine = RejectionEngine(domain, formula, polynomial.to_smt(), self.sample_count)
        result = engine.compute_volume()
        if self.bounding_box:
            result = result
        return result

    def __str__(self):
        return f"xadd_int.{self.sample_count}" + (f".{self.bounding_box}" if self.bounding_box > 0 else "")
