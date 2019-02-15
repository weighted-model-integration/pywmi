from builtins import range
from typing import List

import numpy
import pysmt.shortcuts as smt
import scipy.optimize

from pywmi import evaluate, Domain
from pywmi.engine import Engine
from pywmi.sample import uniform
from pywmi.smt_math import LinearInequality, Polynomial
from .integration_backend import IntegrationBackend


def sample(n_boolean_vars, bounds, n):
    samples = numpy.random.random((n, n_boolean_vars + len(bounds)))
    samples[:, 0:n_boolean_vars] = samples[:, 0:n_boolean_vars] < 0.5

    for d in range(len(bounds)):
        a, b = bounds[d]
        samples[:, n_boolean_vars + d] = a[0] + samples[:, n_boolean_vars + d] * (b[0] - a[0])

    return samples


class RejectionEngine(Engine):
    def __init__(self, domain, support, weight, sample_count, seed=None):
        Engine.__init__(self, domain, support, weight, exact=False)
        if seed is not None:
            numpy.random.seed(seed)
        self.seed = seed
        self.sample_count = sample_count

    def compute_volume(self, sample_count=None, add_bounds=False):
        sample_count = sample_count if sample_count is not None else self.sample_count
        samples = uniform(self.domain, sample_count)
        labels = evaluate(self.domain, self.support, samples)
        bound_volume = self.domain.get_volume() if len(self.domain.real_vars) > 0 else 2 ** len(self.domain.bool_vars)
        approx_volume = bound_volume * sum(labels) / len(labels)

        if self.weight is not None:
            pos_samples = samples[labels]
            sample_weights = evaluate(self.domain, self.weight, pos_samples)
            try:
                return sum(sample_weights) / pos_samples.shape[0] * approx_volume
            except ZeroDivisionError:
                return 0.0
        else:
            return approx_volume

    def compute_probabilities(self, queries, sample_count=None, add_bounds=False):
        sample_count = sample_count if sample_count is not None else self.sample_count
        samples = uniform(self.domain, sample_count)
        labels = evaluate(self.domain, self.support, samples)
        positive_samples = samples[labels]

        results = []
        if self.weight is not None:
            sample_weights = evaluate(self.domain, self.weight, positive_samples)
            total = sum(sample_weights)
            for query in queries:
                if total > 0:
                    query_labels = numpy.logical_and(evaluate(self.domain, query, positive_samples), labels[labels])
                    results.append(sum(sample_weights[query_labels]) / total)
                else:
                    results.append(None)
        else:
            total = positive_samples.shape[0]
            for query in queries:
                if total > 0:
                    query_labels = numpy.logical_and(evaluate(self.domain, query, positive_samples), labels[labels])
                    results.append(sum(query_labels) / total)
                else:
                    results.append(None)

        return results

    def copy(self, domain, support, weight):
        return RejectionEngine(domain, support, weight, self.sample_count, self.seed)

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
                    # noinspection PyTypeChecker
                    lb = scipy.optimize.linprog(c, a_matrix, b_matrix).x[j]
                    # noinspection PyTypeChecker
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
                raise ValueError("Illegal bounding box value {}".format(self.bounding_box))
            domain = Domain(domain.variables, domain.var_types, lb_ub_bounds)

        engine = RejectionEngine(domain, formula, polynomial.to_smt(), self.sample_count)
        result = engine.compute_volume()
        if self.bounding_box:
            result = result
        return result

    def __str__(self):
        return "ref_int.{}".format(self.sample_count)\
               + (".{}".format(self.bounding_box) if self.bounding_box > 0 else "")
