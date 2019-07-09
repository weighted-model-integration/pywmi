import argparse
import os
import random

import pysmt.shortcuts as smt

from pywmi import Domain
from pywmi.domain import Density, FileDensity


def make_domain(n):
    return Domain.make([], ["x"] + ["x{}".format(i) for i in range(n)], [(0, 1) for _ in range(n + 1)])


def flip_domain(domain: Domain):
    return Domain(list(reversed(domain.variables)), domain.var_types, domain.var_domains)


def make_distinct_bounds(domain):
    base_lower_bound = 0.13
    base_upper_bound = 0.89
    step = 0.01
    variables = domain.get_symbols(domain.real_vars)

    bounds = smt.TRUE()
    for i in range(len(variables)):
        bounds &= variables[i] >= base_lower_bound + i * step  # - i * step
        bounds &= variables[i] <= base_upper_bound - i * step  # + i * step

    return bounds


"""
    fun generateXor(terms: Int) : BoolXADD {
        val baseLb = 0.13
        val baseUb = 0.89
        val step = 0.01

        var bounds = build.test("x >= $baseLb").and(build.test("x <= $baseUb"))
        (0 until terms).forEach {
            val lb = build.test("c$it >= " + (baseLb + it * step))
            val ub = build.test("c$it <= " + (baseUb - it * step))
            bounds = bounds.and(lb.and(ub))
        }

        val termList = ArrayList<BoolXADD>()
        (0 until terms).forEach { termList.add(build.test("x <= c$it")) }

        val xor = termList.fold(build.`val`(false)) { cumulative, new ->
            cumulative.xor(new)
        }

        return bounds.and(xor)
    }

"""


def generate_xor(n):
    domain = make_domain(n)
    symbols = domain.get_symbols(domain.real_vars)
    x, symbols = symbols[0], symbols[1:]
    bounds = make_distinct_bounds(domain)
    terms = [x <= v for v in symbols]
    xor = smt.FALSE()
    for term in terms:
        xor = (xor | term) & ~(xor & term)

    flipped_domain = Domain(list(reversed([v for v in domain.variables if v != "x"])) + ["x"], domain.var_types, domain.var_domains)
    return FileDensity(flipped_domain, bounds & xor, smt.Real(1.0))


def generate_mutual_exclusive(n):
    domain = make_domain(n)

    symbols = domain.get_symbols(domain.real_vars)
    x, symbols = symbols[0], symbols[1:]

    bounds = make_distinct_bounds(domain)

    terms = [x <= v for v in symbols]
    disjunction = smt.TRUE()
    for i in range(n):
        for j in range(i + 1, n):
            disjunction &= ~terms[i] | ~terms[j]

    disjunction = smt.simplify(disjunction) & smt.Or(*terms)

    flipped_domain = Domain(list(reversed([v for v in domain.variables if v != "x"])) + ["x"], domain.var_types, domain.var_domains)
    return FileDensity(flipped_domain, disjunction & bounds, smt.Real(1.0))


def generate_dual_paths(n):
    booleans = []  # ["A{}".format(i) for i in range(n)]
    domain = Domain.make(booleans, ["x{}".format(i) for i in range(n)], real_bounds=(0, 1))
    bool_vars = domain.get_bool_symbols()
    real_vars = domain.get_real_symbols()
    terms = []
    for i in range(n):
        v1, v2 = random.sample(real_vars, 2)
        terms.append(v1 * random.random() <= v2 * random.random())

    paths = []
    for i in range(n):
        paths.append(smt.And(*random.sample(bool_vars + terms, n)))

    return Density(domain, domain.get_bounds() & smt.Or(*paths), smt.Real(1))


def generate_dual_paths_distinct(n):
    booleans = []  # ["A{}".format(i) for i in range(n)]
    domain = Domain.make(booleans, ["x{}".format(i) for i in range(n)], real_bounds=(0, 1))
    bool_vars = domain.get_bool_symbols()
    real_vars = domain.get_real_symbols()
    terms = []
    for i in range(n):
        v1, v2 = random.sample(real_vars, 2)
        terms.append(v1 * random.random() <= v2 * random.random())

    paths = []
    for i in range(n):
        paths.append(smt.Ite(smt.And(*random.sample(bool_vars + terms, n)), smt.Real(i), smt.Real(0)))

    return Density(domain, domain.get_bounds(), smt.Plus(*paths))


def generate_click_graph(n):
    def t(c):
        return smt.Ite(c, one, zero)

    sim_n, cl_n, b_n, sim_x_n, b_x_n = "sim", "cl", "b", "sim_x", "b_x"
    domain = Domain.make(
        # Boolean
        ["{}_{}".format(sim_n, i) for i in range(n)]
        + ["{}_{}_{}".format(cl_n, i, j) for i in range(n) for j in (0, 1)]
        + ["{}_{}_{}".format(b_n, i, j) for i in range(n) for j in (0, 1)],
        # Real
        ["{}".format(sim_x_n)]
        + ["{}_{}_{}".format(b_x_n, i, j) for i in range(n) for j in (0, 1)],
        real_bounds=(0, 1)
    )
    sim = [domain.get_symbol("{}_{}".format(sim_n, i)) for i in range(n)]
    cl = [[domain.get_symbol("{}_{}_{}".format(cl_n, i, j)) for j in (0, 1)] for i in range(n)]
    b = [[domain.get_symbol("{}_{}_{}".format(b_n, i, j)) for j in (0, 1)] for i in range(n)]
    sim_x = domain.get_symbol("{}".format(sim_x_n))
    b_x = [[domain.get_symbol("{}_{}_{}".format(b_x_n, i, j)) for j in (0, 1)] for i in range(n)]

    support = smt.And([
        smt.Iff(cl[i][0], b[i][0])
        & smt.Iff(cl[i][1], (sim[i] & b[i][0]) | (~sim[i] & b[i][1]))
        for i in range(n)
    ])

    one = smt.Real(1)
    zero = smt.Real(0)
    w_sim_x = t(sim_x >= 0) * t(sim_x <= 1)
    w_sim = [smt.Ite(s_i, sim_x, 1 - sim_x) for s_i in sim]
    w_b_x = [t(b_x[i][j] >= 0) * t(b_x[i][j] <= 1) for i in range(n) for j in (0, 1)]
    w_b = [smt.Ite(b[i][j], b_x[i][j], 1 - b_x[i][j]) for i in range(n) for j in (0, 1)]

    weight = smt.Times(*([w_sim_x] + w_sim + w_b_x + w_b))
    return FileDensity(domain, support, weight)


def generate_univariate(n):
    domain = Domain.make([], ["x{}".format(i) for i in range(n)], real_bounds=(-2, 2))
    x_vars = domain.get_symbols()
    support = smt.And(*[x > 0.5 for x in x_vars])
    weight = smt.Times(*[smt.Ite((x > -1) & (x < 1), smt.Ite(x < 0, x + smt.Real(1), -x + smt.Real(1)), smt.Real(0))
                         for x in x_vars])
    return FileDensity(domain, support, weight)


def generate_dual(n):
    n = 2*n
    domain = Domain.make([], ["x{}".format(i) for i in range(n)], real_bounds=(0, 1))
    x_vars = domain.get_symbols()
    terms = [x_vars[2 * i] <= x_vars[2 * i + 1] for i in range(int(n / 2))]
    disjunction = smt.Or(*terms)
    for i in range(len(terms)):
        for j in range(i + 1, len(terms)):
            disjunction &= ~terms[i] | ~terms[j]
    return FileDensity(domain, disjunction & domain.get_bounds(), smt.Real(1))


def generate_mspn_tree(n):
    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("problem_name", choices=["xor", "mutex", "click", "uni", "dual", "dual_paths", "dual_paths_distinct"])
    parser.add_argument("size", type=str)
    parser.add_argument("-s", "--seed", default=None)
    parser.add_argument("output_file", default=None)
    args = parser.parse_args()

    if ":" in args.size:
        first, last = args.size.split(":", 1)
        sizes = range(int(first), int(last) + 1)
    else:
        sizes = [int(args.size)]

    problem_name = args.problem_name

    if args.seed is not None and ":" in args.seed:
        first, last = args.seed.split(":", 1)
        seeds = range(int(first), int(last) + 1)
    else:
        seeds = [None if not args.seed else int(args.seed)]

    for seed in seeds:
        for size in sizes:
            if problem_name == "xor":
                density = generate_xor(size)
            elif problem_name == "mutex":
                density = generate_mutual_exclusive(size)
            elif problem_name == "click":
                density = generate_click_graph(size)
            elif problem_name == "uni":
                density = generate_univariate(size)
            elif problem_name == "dual":
                density = generate_dual(size)
            elif problem_name == "dual_paths":
                random.seed(seed)
                density = generate_dual_paths(size)
            elif problem_name == "dual_paths_distinct":
                random.seed(seed)
                density = generate_dual_paths_distinct(size)
            else:
                raise ValueError("No problem with name {}".format(problem_name))

            filename = os.path.join(args.output_file, "{}_{}".format(problem_name, size))
            if seed is not None:
                filename += "_{}".format(seed)
            if not isinstance(density, FileDensity):
                filename += ".json"
            density.to_file(filename)


if __name__ == "__main__":
    main()
