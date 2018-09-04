import argparse
import json
import math
import os
import random
import time

import numpy
from pysmt.shortcuts import Solver, Real, read_smtlib

import parse
from parse import nested_to_smt
import pywmi


def entropy(pos, neg):
    if pos + neg == 0:
        return 1
    p1 = pos / (pos + neg)
    p2 = neg / (pos + neg)
    return - p1 * (math.log2(p1) if p1 != 0 else 0) - p2 * (math.log2(p2) if p2 != 0 else 0)


def information_gain(samples, labels, dimension_index, split_value):
    parent_pos = 0
    parent_neg = 0
    split_true_pos = 0
    split_true_neg = 0
    split_false_pos = 0
    split_false_neg = 0

    for i in range(len(samples)):
        split_true = samples[i][dimension_index] <= split_value
        if labels[i] == 0:
            parent_pos += 1
            if split_true:
                split_true_pos += 1
            else:
                split_false_pos += 1
        else:
            parent_neg += 1
            if split_true:
                split_true_neg += 1
            else:
                split_false_neg += 1

    w_true = (split_true_pos + split_true_neg) / len(labels)
    return entropy(parent_pos, parent_neg)\
           - w_true * entropy(split_true_pos, split_true_neg)\
           - (1 - w_true) * entropy(split_false_pos, split_false_neg)


class Node(object):
    def __init__(self, samples, labels, volume, builder, bounds, empty, split=None, children=()):
        self.samples = samples
        self.labels = labels
        self.volume = volume
        self.builder = builder
        self.bounds = bounds
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

    def get_volume(self, desired_samples=None, total_raw=None):
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
                    new_samples = sample(self.bounds, required_samples)
                    new_labels = self.builder.oracle.check(new_samples)
                    self.samples = numpy.concatenate([self.samples, new_samples])
                    self.labels = numpy.concatenate([self.labels, new_labels])
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

    def get_weighted_volume(self, domain, weight_function):
        if self.is_leaf:
            if not self.empty:
                weighted_count = pywmi.evaluate(domain, weight_function, numpy.array([]), self.samples[self.labels])
                return sum(weighted_count) / len(self.samples) * (self.volume / self.builder.volume)
            return 0
        else:
            return sum(node.get_weighted_volume(domain, weight_function) for node in self.children)


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
        self.solver = Solver()
        self.solver.add_assertion(formula)

    def check(self, samples):
        # Speed up by converting formula to data structure that can quickly check True / False
        # array = numpy.zeros(len(samples))
        # for i in range(len(samples)):
        #     if test(self.formula, {v: samples[i][j] for j, v in enumerate(self.domain.real_vars)}):
        #         array[i] = 1
        array = pywmi.evaluate(self.domain, self.formula, None, samples)
        return array

    def get_accepted_sample(self):
        self.solver.solve()
        try:
            model = self.solver.get_model()
            return [model.get_value(self.domain.get_symbol(var)) for var in self.domain.real_vars]
        except Exception:
            return None

    def add_split(self, split, is_true):
        var = self.domain.get_symbol(self.domain.real_vars[split[0]])
        assertion = var <= split[1] if is_true else var > split[1]
        self.solver.push()
        self.solver.add_assertion(assertion)

    def remove_last_split(self):
        self.solver.pop()


def sample(bounds, n):
    return batch_sample(bounds, n)


def individual_samples(bounds, n):
    samples = numpy.zeros((n, len(bounds)))
    for i in range(n):
        for d in range(len(bounds)):
            a, b = bounds[d]
            s = a[0] + random.random() * (b[0] - a[0])
            while not a[1] and s == a[0]:
                s = a[0] + random.random() * (b[0] - a[0])
            samples[i][d] = s
    return samples


def batch_sample(bounds, n):
    samples = numpy.random.random((n, len(bounds)))
    for d in range(len(bounds)):
        a, b = bounds[d]
        samples[:, d] = a[0] + samples[:, d] * (b[0] - a[0])
    return samples


class TreeBuilder(object):
    def __init__(self, bounds, oracle, stopping_f, scoring_f, sample_count):
        """
        :param bounds: The list of bounds (bound = ((lb, closed?), (ub, closed?)))
        :param oracle: The oracle for verifying inclusion and finding samples
        :param stopping_f: Stopping criterion: f(ratio accepted / all samples, volume) => bool
        :param scoring_f: Scoring function for splits: f(samples, labels, dimension_index, split_value) => float
        :param sample_count: The number of samples to use for testing at every node
        """
        self.bounds = bounds
        self.volume = self.get_volume(bounds)
        self.oracle = oracle
        self.stopping_f = stopping_f
        self.scoring_f = scoring_f
        self.sample_count = sample_count

    @property
    def formula(self):
        return self.oracle.formula

    def build_tree(self, bounds=None, volume=None):
        """
        Builds a sampling tree
        :param bounds: The list of bounds (bound = ((lb, closed?), (ub, closed?)))
        :param volume: The bounds volume
        :return Node: The tree
        """

        if bounds is None:
            bounds = self.bounds
        if volume is None:
            volume = self.get_volume(bounds)

        samples = sample(bounds, self.sample_count)
        labels = self.oracle.check(samples)

        accepted_count = sum(labels)
        # print("Ratio is: {} (bounds={})".format(accepted_count / self.sample_count, bounds))
        if self.stopping_f(accepted_count / self.sample_count, volume / self.volume):
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
            child_1 = self.build_tree(bounds_1, volume / 2)

            self.oracle.remove_last_split()
            bounds_2 = tuple(b if i != split[0] else ((split[1], False), b[1]) for i, b in enumerate(bounds))
            self.oracle.add_split(split, False)
            child_2 = self.build_tree(bounds_2, volume / 2)

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


def compare_methods(domain, support, weights, queries, file_name, n_build=1000, n_total=10000):
    import subprocess

    def error(_exact_volume, _volume):
        return abs(_volume - _exact_volume) / abs(_exact_volume) if _exact_volume != 0 else 0

    def r_duration(_reference_time, _duration):
        return _duration / _reference_time if _reference_time != 0 else 0

    def run_wmi(_timeout=None):
        wmi_python = "/Users/samuelkolb/Documents/PhD/wmi-pa/env/bin/python"
        wmi_client = "/Users/samuelkolb/Documents/PhD/wmi-pa/experiments/client/run.py"
        output = str(subprocess.check_output([wmi_python, wmi_client, "-f", file_name, "-v"], timeout=_timeout))
        wmi_volume = float(str(output)[9:-3])
        return wmi_volume

    def run_xadd(mode, _timeout=None):
        class_path = "/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/charsets.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/deploy.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/ext/cldrdata.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/ext/dnsns.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/ext/jaccess.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/ext/jfxrt.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/ext/localedata.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/ext/nashorn.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/ext/sunec.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/ext/sunjce_provider.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/ext/sunpkcs11.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/ext/zipfs.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/javaws.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/jce.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/jfr.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/jfxswt.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/jsse.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/management-agent.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/plugin.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/resources.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/rt.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/lib/ant-javafx.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/lib/dt.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/lib/javafx-mx.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/lib/jconsole.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/lib/packager.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/lib/sa-jdi.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/lib/tools.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/out/production/XADD:/Users/samuelkolb/Documents/PhD/WMI/XADD/out/production/Util:/Users/samuelkolb/Documents/PhD/WMI/XADD/out/production/xadd-inference:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/trueskill/lombok.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/trueskill/lombok.zip:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/trueskill/testng.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/trueskill/testng.zip:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/trueskill/ejml-0.11.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/trueskill/ejml-0.11-src.zip:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/batik-awt-util-1.7.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/batik-svggen-1.7.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/batik-util-1.7.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/grappa1_4.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/java_cup.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/jlex.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/jmatio.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/junit-4.7.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/liblinear-1.8.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/PlotPackage.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/surfaceplot.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/xml-apis-1.3.04.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/colt-1.2.0.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/commons-beanutils-1.7.0.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/commons-digester-1.8.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/architecture-rules-2.1.1.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/commons-lang3-3.2.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/commons-logging-1.1.1.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/commons-math3-3.3.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/concurrent-1.3.4.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/csparsej-1.1.1.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/GLPKSolverPack.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/hamcrest-core-1.3.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/javassist-3.0.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/jdepend-2.9.1.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/joptimizer-3.5.0.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/log4j-1.2.14.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/SCPSolver.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/utils-1.07.00.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/LPSOLVESolverPack.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/gurobi.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/architecture-rules-2.1.1.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/colt-1.2.0.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/commons-beanutils-1.7.0.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/commons-digester-1.8.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/commons-lang3-3.2.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/commons-logging-1.1.1.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/commons-math3-3.3.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/concurrent-1.3.4.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/csparsej-1.1.1.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/GLPKSolverPack.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/hamcrest-core-1.3.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/javassist-3.0.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/jdepend-2.9.1.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/joptimizer-3.5.0.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/log4j-1.2.14.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/SCPSolver.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/utils-1.07.00.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/kotlin-reflect.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/kotlin-stdlib.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/LPSOLVESolverPack.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/gurobi.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/gson-2.6.2.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/json.jar"
        output = str(subprocess.check_output(["java", "-classpath", class_path, "diagram.QueryEngineKt", file_name, mode], timeout=_timeout))
        xadd_volume = float(output.split("\\n")[-3].split(" ")[0])
        return xadd_volume

    def run_tree(_timeout=None):
        start_build = time.time()
        tree = builder.build_tree()
        end_build = time.time()
        tree_volume = tree.get_volume(n_total)
        end_volume = time.time()
        if weights is not None:
            tree_volume = tree.get_weighted_volume(domain, weights)
            end_weighted = time.time()
            # print(end_build - start_build, end_volume - end_build, end_weighted - end_volume)
        print("Empty: {:.2f}%".format(tree.get_empty_volume() * 100))
        return tree_volume * builder.volume

    def run_rejection(_timeout=None):
        rejection_samples = sample(bounds, n_total)
        labels = oracle.check(rejection_samples)
        if weights is not None:
            sample_weights = pywmi.evaluate(domain, weights, numpy.array([]), rejection_samples[labels])
            rejection_volume = sum(sample_weights) / len(labels) * builder.volume
        else:
            rejection_volume = sum(labels) / len(labels) * builder.volume
        return rejection_volume

    bounds = tuple(((domain.var_domains[var][0], True), (domain.var_domains[var][1], True)) for var in domain.real_vars)
    oracle = SmtOracle(support & queries[0], domain)

    def stop(ratio, volume):
        return ratio >= 0.5 or volume <= 0.001

    builder = TreeBuilder(bounds, oracle, stop, information_gain, n_build)
    modes = [
        # ("WMI", run_wmi, True),
        # ("X-R", lambda t: run_xadd("resolve", t), True),
        # ("X-M", lambda t: run_xadd("mass", t), True),
        # ("X-O", lambda t: run_xadd("original", t), True),
        ("Tree", run_tree, False),
        ("Rej.", run_rejection, False),
    ]

    print("Method\tTime\tR Time\tError\tStd.Dev\tVolume")

    exact_volume = None
    reference_duration = None
    timeout = 100
    for name, f, exact in modes:
        durations = []
        volumes = []
        for i in range(1 if exact else 10):
            start_time = time.time()
            try:
                volume = f(max(timeout, int(reference_duration) + 1 if reference_duration is not None else 0))
                end_time = time.time()
                duration = end_time - start_time
                if exact_volume is None and exact:
                    exact_volume = volume
                    reference_duration = duration
            except subprocess.TimeoutExpired:
                duration = timeout
                volume = 0
            durations.append(duration)
            volumes.append(volume)
        average_duration = sum(durations) / len(durations)
        r_time = r_duration(reference_duration, average_duration) if reference_duration is not None else 0
        average_volume = sum(volumes) / len(volumes)
        deviation = math.sqrt(sum((v - average_volume) ** 2 for v in volumes) / len(volumes))
        if exact_volume is None:
            err = 0
        else:
            err_list = [error(exact_volume, v) for v in volumes]
            err = sum(err_list) / len(err_list)
        print("{}\t{:.2f}\t{:.2f}\t{:.2f}\t{:.2f}\t{}".format(name, average_duration, r_time, err, deviation, average_volume))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("-c", "--convert", default=None, type=str, help="Convert the source from a different format.")
    args = parser.parse_args()

    json_file = args.file + ".converted.json"
    if args.convert is None or os.path.exists(json_file):
        with open(args.file if args.convert is None else json_file) as f:
            flat = json.load(f)

        domain = pywmi.import_domain(flat["domain"])
        queries = [nested_to_smt(query) for query in flat["queries"]]
        support = nested_to_smt(flat["formula"])
        weights = nested_to_smt(flat["weights"]) if "weights" in flat else None

    elif args.convert == "smt_synthetic":
        with open(args.file) as f:
            flat = json.load(f)

        domain = pywmi.import_domain(flat["synthetic_problem"]["problem"]["domain"])
        queries = [nested_to_smt(flat["synthetic_problem"]["problem"]["theory"])]
        support = domain.get_bounds()
        weights = Real(1)

    elif args.convert == "wmi_generate_tree":
        queries = [read_smtlib(args.file + "_0.query")]
        support = read_smtlib(args.file + "_0.support")
        weights = read_smtlib(args.file + "_0.weights")
        variables = queries[0].get_free_variables() | support.get_free_variables() | weights.get_free_variables()
        domain = pywmi.Domain.make(real_variable_bounds={v.symbol_name(): [0, 1] for v in variables})

    elif args.convert == "wmi_mspn":
        q_file, s_file, w_file = ("{}.{}".format(args.file, ext) for ext in ["query", "support", "weights"])
        queries = [] if not os.path.exists(q_file) else [read_smtlib(q_file)]
        support = read_smtlib(s_file)
        weights = read_smtlib(w_file)
        variables = support.get_free_variables() | weights.get_free_variables()
        for query in queries:
            variables |= query.get_free_variables()
        # TODO Future work: detect bounds
        domain = pywmi.Domain.make(real_variable_bounds={v.symbol_name(): [0, 1] for v in variables})
    else:
        raise ValueError("Invalid conversion: {}".format(args.convert))

    if args.convert is not None:
        flat = {
            "domain": pywmi.export_domain(domain, False),
            "queries": [parse.smt_to_nested(query) for query in queries],
            "formula": parse.smt_to_nested(support),
            "weights": parse.smt_to_nested(weights)
        }

        with open(json_file, "w") as f:
            json.dump(flat, f)
    else:
        json_file = args.file

    compare_methods(domain, support, weights, queries, json_file)
