import itertools
import platform
from typing import Union, Optional, List, Tuple, Dict, Set

import matplotlib as mpl
import numpy as np
import polytope
import pysmt.shortcuts as smt

from pysmt.fnode import FNode
from pysmt.typing import REAL

from pywmi import Domain, SmtWalker

if platform.system() == "Darwin":
    mpl.use('TkAgg')

import matplotlib.pyplot as plt


class RegionBuilder(SmtWalker):
    def __init__(self, domain):
        self.domain = domain

    def get_bounded_region(self, in_c, in_b):
        coefficients = np.zeros([len(self.domain.real_vars) * 2 + 1, len(self.domain.real_vars)])
        b = np.zeros(len(self.domain.real_vars) * 2 + 1)
        for i in range(len(self.domain.real_vars)):
            coefficients[2 * i, i] = -1
            coefficients[2 * i + 1, i] = 1

            lb, ub = self.domain.var_domains[self.domain.real_vars[i]]
            b[2 * i] = -lb
            b[2 * i + 1] = ub

        coefficients[-1, :] = in_c
        b[-1] = in_b

        return polytope.Region([polytope.Polytope(coefficients, b)])

    def walk_and(self, args):
        regions = self.walk_smt_multiple(args)
        region = regions[0]
        for i in range(1, len(regions)):
            region = region.intersect(regions[i])
        return region

    def walk_or(self, args):
        regions = self.walk_smt_multiple(args)
        region = regions[0]
        for i in range(1, len(regions)):
            region = region.union(regions[i])
        return region

    def walk_plus(self, args):
        coefficients = dict()
        for arg in self.walk_smt_multiple(args):
            if not isinstance(arg, dict) and isinstance(arg, str):
                arg = {arg: 1}
            coefficients.update(arg)
        return coefficients

    def walk_minus(self, left, right):
        raise RuntimeError("Should not encounter minus")

    def walk_times(self, args):
        args = self.walk_smt_multiple(args)
        if len(args) != 2:
            raise RuntimeError("Something went wrong, expected 2 arguments but got {}".format(args))
        if isinstance(args[0], str):
            return {args[0]: args[1]}
        else:
            return {args[1]: args[0]}

    def walk_not(self, argument):
        return self.get_bounded_region(np.zeros(len(self.domain.real_vars)), 0) - self.walk_smt(argument)

    def walk_ite(self, if_arg, then_arg, else_arg):
        raise RuntimeError("Should not encounter ite")

    def walk_pow(self, base, exponent):
        raise RuntimeError("Should not encounter power")

    def walk_lte(self, left, right):
        left, right = self.walk_smt_multiple((left, right))
        if isinstance(right, str):
            right = {right: 1.0}

        if isinstance(left, str):
            left = {left: 1.0}

        if isinstance(right, dict):
            t = right
            right = left
            left = t
            right = -right
            left = {v: -val for v, val in left.items()}

        coefficients = np.array([left[v] if v in left else 0.0 for v in self.domain.real_vars])

        inequality = self.get_bounded_region(coefficients, right)
        return inequality

    def walk_lt(self, left, right):
        return self.walk_lte(left, right)

    def walk_equals(self, left, right):
        raise RuntimeError("Should not encounter equals")

    def walk_symbol(self, name, v_type):
        return name

    def walk_constant(self, value, v_type):
        if v_type == REAL:
            return float(value)

        whole = self.get_bounded_region(np.zeros(len(self.domain.real_vars)), 0)
        if value:
            return whole
        else:
            return whole - whole


def plot_formula(name, domain, formula, features=None):
    if features is None or (features[0] is None and features[1] is None):
        features = (domain.real_vars[0], domain.real_vars[1])
    elif features[1] is None:
        features = (features[0], features[0])
    plot_combined(features[0], features[1], domain, formula, [], None, name, set(), set(), None)


def plot_data(name, domain, data, formula=None, features=None):
    if features is None:
        features = (domain.real_vars[0], domain.real_vars[1])
    plot_combined(features[0], features[1], domain, formula, data, None, name, set(), set(), None)


def plot_combined(feat_x, feat_y, domain, formula, data, learned_labels, name, active_indices, new_active_indices,
                  condition=None):
    # type: (Union[str, int], Union[str, int], Domain, FNode, Union[np.ndarray, List[Tuple[Dict, bool]]], Optional[List[bool]], str, Set[int], Set[int], Optional[callable]) -> None

    row_vars = domain.bool_vars[:int(len(domain.bool_vars) / 2)]
    col_vars = domain.bool_vars[int(len(domain.bool_vars) / 2):]
    sf_size = 2

    fig = plt.figure(num=None, figsize=(2 ** len(col_vars) * sf_size, 2 ** len(row_vars) * sf_size), dpi=300)

    for assignment in itertools.product([True, False], repeat=len(domain.bool_vars)):
        row = 0
        for b in assignment[:len(row_vars)]:
            row = row * 2 + (1 if b else 0)

        col = 0
        for b in assignment[len(row_vars):]:
            col = col * 2 + (1 if b else 0)

        index = row * (2 ** len(col_vars)) + col
        ax = fig.add_subplot(2 ** len(row_vars), 2 ** len(col_vars), 1 + index)

        if formula is not None:
            substitution = {domain.get_symbol(v): smt.Bool(a) for v, a in zip(domain.bool_vars, assignment)}
            substituted = formula.substitute(substitution)
            region = RegionBuilder(domain).walk_smt(substituted)
            try:
                if region.dim == 2:
                    region.linestyle = None
                    region.plot(ax=ax, color="green", alpha=0.2)
            except IndexError:
                pass

        points = []

        def status(_i):
            return "active" if _i in active_indices else ("new_active" if _i in new_active_indices else "excluded")

        if isinstance(data, np.ndarray):
            var_index_map = domain.var_index_map()
            feat_x, feat_y = (f if isinstance(f, str) else var_index_map[f] for f in (feat_x, feat_y))
            for i in range(data.shape[0]):
                row = data[i, :-1]
                point = row[feat_x], row[feat_y]
                label = data[i, len(domain.variables)] == 1
                correct = (learned_labels[i] == label) if learned_labels is not None else True
                match = all(row[var_index_map[v]] == a for v, a in zip(domain.bool_vars, assignment))
                if match and (condition is None or condition(row, label)):
                    points.append((label, correct, status(i), point))
        else:
            for i in range(len(data)):
                instance, label = data[i]
                point = (float(instance[feat_x]), float(instance[feat_y]))
                correct = (learned_labels[i] == label) if learned_labels is not None else True
                match = all(instance[v] == a for v, a in zip(domain.bool_vars, assignment))
                if match and (condition is None or condition(instance, label)):
                    points.append((label, correct, status(i), point))

        def get_color(_l, _c, _s):
            if _s == "active":
                return "black"
            return "green" if _l else "red"

        def get_marker(_l, _c, _s):
            # if _s == "active":
            #     return "v"
            return "+" if _l else "."

        def get_alpha(_l, _c, _s):
            if _s == "active":
                return 0.5
            elif _s == "new_active":
                return 1
            elif _s == "excluded":
                return 0.2

        for label in [True, False]:
            for correct in [True, False]:
                for status in ["active", "new_active", "excluded"]:
                    marker, color, alpha = [f(label, correct, status) for f in (get_marker, get_color, get_alpha)]
                    selection = [p for l, c, s, p in points if l == label and c == correct and s == status]
                    if len(selection) > 0:
                        ax.scatter(*zip(*selection), c=color, marker=marker, alpha=alpha)

        ax.set_xlim(domain.var_domains[feat_x])
        ax.set_ylim(domain.var_domains[feat_y])

    if name is not None:
        plt.savefig(name if name.endswith(".png") else "{}.png".format(name))
    else:
        plt.show()
    plt.close(fig)
