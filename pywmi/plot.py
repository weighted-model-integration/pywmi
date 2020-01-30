import itertools
import platform
from typing import Union, Optional, List, Tuple, Dict, Set

import matplotlib as mpl
import numpy as np
import polytope
import pysmt.shortcuts as smt


from pysmt.fnode import FNode
from pysmt.typing import REAL

from pywmi import Domain, SmtWalker, Density, evaluate
from .smt_math import LinearInequality

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
        inequality = LinearInequality.from_smt(left <= right)

        coefficients = np.array([inequality.coefficient(v) for v in self.domain.real_vars])

        inequality = self.get_bounded_region(coefficients, inequality.b())
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


def plot_combined(feat_x: Union[str, int],
                  feat_y: Union[str, int],
                  domain: Domain,
                  formula: Optional[FNode],
                  data: Union[Tuple[np.ndarray, np.ndarray], List[Tuple[Dict, bool]]],
                  learned_labels: Optional[List[bool]],
                  name: str,
                  active_indices: Set[int],
                  new_active_indices: Set[int],
                  condition: Optional[callable]=None):

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
            substituted = smt.simplify(formula.substitute(substitution))
            try:
                region = RegionBuilder(domain).walk_smt(substituted)
                try:
                    if region.dim == 2:
                        region.linestyle = None
                        region.plot(ax=ax, color="green", alpha=0.2)
                except IndexError:
                    pass
            except ValueError:
                pass

        points = []

        def status(_i):
            return "active" if _i in active_indices else ("new_active" if _i in new_active_indices else "excluded")

        if isinstance(data, tuple):
            values, labels = data  # type: Tuple[np.ndarray, np.ndarray]
            var_index_map = domain.var_index_map()
            fx, fy = (f if isinstance(f, int) else var_index_map[f] for f in (feat_x, feat_y))
            # noinspection PyUnresolvedReferences
            for i in range(values.shape[0]):
                row = values[i, :]
                point = row[fx], row[fy]
                label = labels[i] == 1
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


def plot_density(density: Density, feat_x: Optional[str] = None, feat_y: Optional[str] = None,
                 filename: Optional[str] = None, d3=False, cmap=None):
    cmap = cmap or "plasma"
    from matplotlib import cm
    from mpl_toolkits.mplot3d import axes3d, Axes3D

    domain = density.domain
    row_vars = domain.bool_vars[:int(len(domain.bool_vars) / 2)]
    col_vars = domain.bool_vars[int(len(domain.bool_vars) / 2):]
    sf_size = 2

    fig = plt.figure(num=None, figsize=(2 ** len(col_vars) * sf_size, 2 ** len(row_vars) * sf_size), dpi=300)
    feat_x = feat_x if feat_x else domain.real_vars[0]
    feat_y = feat_y if feat_y else domain.real_vars[1]

    if d3:
        ax = fig.add_subplot(1, 1, 1, projection='3d')
    else:
        ax = fig.add_subplot(1, 1, 1)

    assert len(domain.bool_vars) == 0  # Otherwise the max and min have to be calculated globally

    support = smt.simplify(density.support)
    weight = smt.simplify(density.weight)

    if d3:
        n = 1000
    else:
        n = 100
    x_arr = np.linspace(domain.var_domains[feat_x][0], domain.var_domains[feat_x][1], n)
    y_arr = np.linspace(domain.var_domains[feat_y][0], domain.var_domains[feat_y][1], n)

    x, y = np.meshgrid(x_arr, y_arr)
    z = np.zeros(x.shape)
    for i in range(x.shape[1]):
        data = np.concatenate((x[:, i][:, np.newaxis], y[:, i][:, np.newaxis]), axis=1)
        labels = evaluate(domain, support, data)
        z[:, i] = evaluate(domain, weight, data) * labels

    if d3:
        ax.plot_surface(x, y, z, cmap=cmap)
        ax.view_init(30, 70)
    else:
        ax.scatter(x, y, c=z, cmap=cmap, s=1)

    plt.tick_params(axis='both', which='major', labelsize=6)
    ax.set_xlim(domain.var_domains[feat_x])
    ax.set_ylim(domain.var_domains[feat_y])

    if filename is not None:
        plt.savefig(filename if filename.endswith(".png") else "{}.png".format(filename))
    else:
        plt.show()
    plt.close(fig)
