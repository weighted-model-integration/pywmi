import math
import numpy as np
from pysmt.exceptions import PysmtException

from pywmi.engine import Engine
from pywmi import evaluate, Domain
import pysmt.shortcuts as smt

from pywmi.sample import uniform

from typing import Tuple


class Oracle(object):
    def __init__(self, formula):
        self.formula = formula

    def check(self, samples):
        raise NotImplementedError()

    def get_accepted_sample(self):
        raise NotImplementedError()

    def add_split(self, split, is_true):
        raise NotImplementedError()

    def remove_last_split(self):
        raise NotImplementedError


class SmtOracle(Oracle):
    def __init__(self, formula, domain):
        super().__init__(formula)
        self.domain = domain
        self.solver = smt.Solver()
        self.solver.add_assertion(formula)

    def check(self, samples):
        return evaluate(self.domain, self.formula, samples)

    def get_accepted_sample(self):
        self.solver.solve()
        try:
            model = self.solver.get_model()
            return np.array([model.get_value(self.domain.get_symbol(var)) for var in self.domain.variables])
        except PysmtException:
            return None

    def add_split(self, split, is_true):
        var = self.domain.get_symbol(self.domain.real_vars[split[0]])
        assertion = var <= split[1] if is_true else var > split[1]
        self.solver.push()
        self.solver.add_assertion(assertion)

    def remove_last_split(self):
        self.solver.pop()


class Node(object):
    def __init__(self, samples, labels, volume, builder, bounds, empty, split=None, children=()):
        self.samples = samples
        self.labels = labels
        self.volume = volume
        self.builder = builder
        self.bounds = bounds
        domain_bounds = {v: (t[0][0], t[1][0]) for v, t in zip(self.builder.domain.real_vars, bounds)}
        self.domain = self.builder.domain.change_bounds(domain_bounds)
        self.empty = empty
        self.split = split  # (dimension_index, value)
        self.children = children

    @property
    def is_leaf(self):
        return len(self.children) == 0

    def accepted_count(self):
        if self.empty:
            return 0
        else:
            return sum(self.labels)

    def get_volume(self, desired_samples=None, total_raw=None, query=None):
        # if desired_samples is not None and total_raw is None:
        #     return self.get_volume(desired_samples, self.get_volume())

        if self.empty:
            return 0

        if self.is_leaf:
            # raw_volume = self.accepted_count() / len(self.labels) * (self.volume / self.builder.volume)
            if desired_samples is not None:
                if total_raw == 0:
                    required_samples = 0
                else:
                    # required_samples = int(math.ceil(desired_samples * raw_volume / total_raw - len(self.samples)))
                    required_samples = int(math.ceil(desired_samples - len(self.samples)))
                # print("Required: " + str(required_samples))
                if required_samples > 0:
                    new_samples = uniform(self.domain, required_samples)
                    new_labels = self.builder.oracle.check(new_samples)
                    self.samples = np.concatenate([self.samples, new_samples])
                    self.labels = np.concatenate([self.labels, new_labels])
                # return self.accepted_count() / len(self.labels) * (self.volume / self.builder.volume)
            # else:
            #     return raw_volume
            return self.accepted_count() / len(self.labels) * (self.volume / self.builder.volume)
        else:
            return sum(node.get_volume(desired_samples=desired_samples, total_raw=total_raw) for node in self.children)

    def get_empty_volume(self):
        if self.is_leaf and self.empty:
            return self.volume / self.builder.volume
        else:
            return sum(node.get_empty_volume() for node in self.children)

    def get_weighted_volume(self, weight_function, query=None):
        if self.is_leaf:
            if not self.empty:
                labels = self.labels
                if query:
                    labels = np.logical_and(evaluate(self.builder.domain, query, self.samples), labels)
                weighted_count = evaluate(self.builder.domain, weight_function, self.samples[labels])
                return sum(weighted_count) / len(self.samples) * (self.volume / self.builder.volume)
            return 0
        else:
            return sum(node.get_weighted_volume(weight_function, query) for node in self.children)

    def __str__(self):
        return self.pretty_print()

    def pretty_print(self, depth=0):
        prefix = "  " * depth
        if self.is_leaf:
            if self.empty:
                node_string = "[E]\n"
            else:
                ratio = self.accepted_count() / len(self.labels)
                node_string = "[{} * {}]\n".format(ratio, self.volume / self.builder.volume)
            return prefix + node_string
        else:
            i, v = self.split
            node_string = "[{} <= {}]\n".format(self.builder.domain.variables[i], v)
            left = self.children[0].pretty_print(depth + 1)
            right = self.children[1].pretty_print(depth + 1)
            return prefix + node_string + left + right


class TreeBuilder(object):
    def __init__(self, domain, oracle, stopping_f, scoring_f, sample_count):
        """
        :param Domain domain: The list of bounds (bound = ((lb, closed?), (ub, closed?)))
        :param Oracle oracle: The oracle for verifying inclusion and finding samples
        :param Callable stopping_f: Stopping criterion: f(ratio accepted / all samples, volume) => bool
        :param Callable scoring_f: Scoring function for splits: f(samples, labels, dimension_index, split_value) => float
        :param int sample_count: The number of samples to use for testing at every node
        """
        self.domain = domain
        self.bounds = tuple(((domain.var_domains[var][0], True), (domain.var_domains[var][1], True))
                            for var in domain.real_vars)
        self.volume = self.get_volume(self.bounds)
        self.oracle = oracle
        self.stopping_f = stopping_f
        self.scoring_f = scoring_f
        self.sample_count = sample_count

    @property
    def formula(self):
        return self.oracle.formula

    def build_tree(self, bounds=None, volume=None, depth=0):
        """
        Builds a sampling tree
        :param Tuple bounds: The list of bounds (bound = ((lb, closed?), (ub, closed?)))
        :param float volume: The bounds volume
        :param int depth: The depth of the current tree
        :return Node: The tree
        """

        if bounds is None:
            bounds = self.bounds
            domain = self.domain
        else:
            domain = self.domain.change_bounds({v: (t[0][0], t[1][0]) for v, t in zip(self.domain.real_vars, bounds)})

        if volume is None:
            volume = self.get_volume(bounds)

        samples = uniform(domain, self.sample_count)
        labels = self.oracle.check(samples)

        accepted_count = sum(labels)
        # print("Ratio is: {} (bounds={})".format(accepted_count / self.sample_count, bounds))
        if self.stopping_f(accepted_count / self.sample_count, volume / self.volume, depth):
            if accepted_count / self.sample_count >= 0.5:
                pass  # print("Stopping because sufficient samples ({} / {}) with volume={}".format(accepted_count, self.sample_count, volume))
            else:
                pass  # print("Stopping because insufficient volume ({})".format(volume))
            return Node(samples, labels, volume, self, bounds, False)  # Sufficiently full region

        if accepted_count > 0 or self.oracle.get_accepted_sample() is not None:
            split = None
            score = None
            for i in range(len(bounds)):
                lb, ub = bounds[i][0][0], bounds[i][1][0]
                split_value = lb + (ub - lb) / 2
                if accepted_count < self.sample_count:
                    split_score = self.scoring_f(samples, labels, i, split_value)
                else:
                    split_score = ub - lb
                if score is None or split_score > score:
                    split = (i, split_value)
                    score = split_score

            # print("Splitting on {} <= {} (volume={})".format(split[0], split[1], volume))
            bounds_1 = tuple(b if i != split[0] else (b[0], (split[1], True)) for i, b in enumerate(bounds))
            self.oracle.add_split(split, True)
            child_1 = self.build_tree(bounds_1, volume / 2, depth + 1)

            self.oracle.remove_last_split()
            bounds_2 = tuple(b if i != split[0] else ((split[1], False), b[1]) for i, b in enumerate(bounds))
            self.oracle.add_split(split, False)
            child_2 = self.build_tree(bounds_2, volume / 2, depth + 1)

            # print("Done splitting on {} <= {} (volume={})".format(split[0], split[1], volume))
            return Node(samples, labels, volume, self, bounds, False, split, (child_1, child_2))  # Splitting region

        # print("Stopping because no samples, volume={}".format(volume))
        return Node(samples, labels, volume, self, bounds, True)  # Empty region

    @staticmethod
    def get_volume(bounds):
        if bounds is None or len(bounds) == 0:
            return None

        volume = 1
        for lb_bound, ub_bound in bounds:
            volume *= ub_bound[0] - lb_bound[0]
        return volume


def entropy(pos, neg):
    if pos + neg == 0:
        return 1
    p1 = pos / (pos + neg)
    p2 = neg / (pos + neg)
    return - p1 * (math.log2(p1) if p1 != 0 else 0) - p2 * (math.log2(p2) if p2 != 0 else 0)


def information_gain(samples, labels, dimension_index, split_value):
    samples_split_true = samples[:, dimension_index] <= split_value
    parent_pos = sum(labels)
    parent_neg = len(labels) - parent_pos

    split_true_pos = sum(np.logical_and(samples_split_true, labels))
    split_true_neg = sum(np.logical_and(samples_split_true, np.logical_not(labels)))
    split_false_pos = parent_pos - split_true_pos
    split_false_neg = parent_neg - split_true_neg

    w_true = (split_true_pos + split_true_neg) / len(labels)
    return entropy(parent_pos, parent_neg) \
        - w_true * entropy(split_true_pos, split_true_neg) \
        - (1 - w_true) * entropy(split_false_pos, split_false_neg)


class AdaptiveRejection(Engine):
    def __init__(self, domain, support, weight, sample_count, sample_count_build=None, stop_criterion=None,
                 split_criterion=None):
        super().__init__(domain, support, weight, False)

        self.sample_count = sample_count
        self.sample_count_build = int(sample_count_build or sample_count / 10)
        self.stop_criterion = stop_criterion or self.make_stop_criterion(max_ratio=0.5, max_depth=6)
        self.split_criterion = split_criterion or information_gain
        oracle = SmtOracle(support, domain)
        self.builder = TreeBuilder(domain, oracle, self.stop_criterion, self.split_criterion, self.sample_count_build)
        self._tree = None

    @staticmethod
    def make_stop_criterion(max_ratio=None, min_volume=None, max_depth=None):
        def f(ratio, volume, depth):
            return (max_ratio is not None and ratio >= max_ratio)\
                   or (min_volume is not None and volume <= min_volume)\
                   or (max_depth is not None and depth >= max_depth)
        return f

    @property
    def tree(self):
        if not self._tree:
            self._tree = self.builder.build_tree()
        return self._tree

    def compute_volume(self, sample_count=None):
        sample_count = sample_count or self.sample_count
        volume = self.tree.get_volume(sample_count)
        if self.weight and self.weight != smt.Real(1):
            return self.tree.get_weighted_volume(self.weight) * self.tree.builder.volume
        else:
            return volume * self.tree.builder.volume

    def compute_probability(self, query, sample_count=None):
        sample_count = sample_count or self.sample_count
        volume = self.tree.get_volume(sample_count)
        if self.weight and self.weight != smt.Real(1):
            return self.tree.get_weighted_volume(self.weight, query) / self.tree.get_weighted_volume(self.weight)
        else:
            return self.tree.get_volume(query=query) / volume

    def get_samples(self, n):
        raise NotImplementedError()

    def copy(self, domain, support, weight):
        return AdaptiveRejection(domain, support, weight, self.sample_count, self.sample_count_build,
                                 self.stop_criterion, self.split_criterion)

    def __str__(self):
        return "adapt:n{}:b{}".format(self.sample_count, self.sample_count_build)
