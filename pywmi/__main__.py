import argparse
import json
import logging
import os
import time
from typing import Set, Tuple, Any, List, Dict

import numpy as np
import tabulate
from pysmt.fnode import FNode
from pysmt.typing import REAL, BOOL

from pywmi import nested_to_smt, import_domain, Domain, export_domain, smt_to_nested, RejectionEngine, \
    PredicateAbstractionEngine, XaddEngine, Engine
from pysmt.shortcuts import read_smtlib, Real

logger = logging.getLogger(__name__)


def parse_options(option_strings, *whitelist):
    # type: (List[str], List[str]) -> Dict[str, Any]

    whitelist = set(whitelist)
    options = {}
    for option_string in option_strings:
        if option_string.startswith("t"):
            n, v = "timeout", int(option_string[1:])
        elif option_string.startswith("n"):
            n, v = "sample_count", int(option_string[1:])
        elif option_string.startswith("m"):
            n, v = "mode", option_string[1:]
        else:
            raise ValueError("Unknown option {}".format(option_string))
        if n in whitelist:
            options[n] = v
        else:
            logger.warning("Ignoring option {}=".format(n, v))
    return options


def get_engine(description, domain, support, weight):
    # type: (str, Domain, FNode, FNode) -> Engine
    parts = description.split(":")

    if parts[0].lower() == "pa":
        options = parse_options(parts[1:], "timeout")
        return PredicateAbstractionEngine(domain, support, weight, **options)
    if parts[0].lower() == "rej":
        options = parse_options(parts[1:], "sample_count")
        return RejectionEngine(domain, support, weight, **options)
    if parts[0].lower() == "xadd":
        options = parse_options(parts[1:], "mode")
        return XaddEngine(domain, support, weight, **options)


def compare(engines):
    def mean(sequence):
        return sum(sequence) / len(sequence)

    def std(sequence):
        return np.std(np.array(sequence))

    def error(_exact_volume, _volume):
        if _exact_volume is None:
            return "-"
        return "{:.4f}".format(abs(_volume - _exact_volume) / abs(_exact_volume) if _exact_volume != 0 else 0)

    def r_duration(_reference_time, _duration):
        if _reference_time is None:
            return "-"
        return "{:.2f}".format(_duration / _reference_time if _reference_time != 0 else 0)

    def d_string(_d):
        return "{:.2f}s".format(_d) if _d is not None else ""

    def vol_string(_v):
        return "{:.4f}".format(_v) if _v is not None else ""

    exact_volumes = []
    exact_durations = []
    delta = 10 ** -5

    header = ["Engine", "Time", "R Time", "Volume", "Error", "Std.Dev"]
    stats = []
    for i, engine in enumerate(engines):
        print("Running engine {} of {}: {: <70}".format(i + 1, len(engines), str(engine)), end="\r", flush=True)

        results = []
        durations = []
        volumes = []

        for i in range(1 if engine.exact else 10):
            start_time = time.time()
            volumes.append(engine.compute_volume())
            durations.append(time.time() - start_time)

            if engine.exact:
                exact_volumes.append((i, volumes[-1]))
                exact_durations.append((i, durations[-1]))

        stats.append([engine, mean(durations), mean(volumes), std(volumes)])

    disagree = False
    for i in range(len(exact_volumes) - 1):
        for j in range(i + 1, len(exact_volumes)):
            if abs(exact_volumes[i][1] - exact_volumes[j][1]) > delta:
                logger.warning("Exact solvers disagree on volume: {} ({}) vs {} ({})"
                               .format(engines[i], exact_volumes[i], engines[j], exact_volumes[j]))
                disagree = True

    ev = None if disagree or len(exact_volumes) == 0 else exact_volumes[0][1]
    fd = None if len(exact_durations) == 0 else min(exact_durations, key=lambda t: t[1])[1]

    stats = [[str(e), d_string(d), r_duration(fd, d), vol_string(v), error(ev, v), std_v]
             for e, d, v, std_v in stats]

    print(tabulate.tabulate(stats, headers=header))


def parse():
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    task_parsers = parser.add_subparsers(dest="task", help="Which task to run")

    vp = task_parsers.add_parser("volume")
    vp.add_argument("engine", help="The engine to use, e.g., pa:t<timeout>, rej:n<samples>")

    cp = task_parsers.add_parser("convert")
    cp.add_argument("json_file", help="The output path for the json file", default=None)

    compare_p = task_parsers.add_parser("compare")
    compare_p.add_argument("engines", help="The engines to compare (see engine input format)", nargs="+")

    parser.add_argument("-d", "--dialect", default=None, type=str, help="The dialect to use for import")
    args = parser.parse_args()

    if args.dialect is None:
        with open(args.file) as f:
            flat = json.load(f)

        domain = import_domain(flat["domain"])
        queries = [nested_to_smt(query) for query in flat["queries"]]
        support = nested_to_smt(flat["formula"])
        weights = nested_to_smt(flat["weights"]) if "weights" in flat else None

    elif args.dialect == "smt_synthetic":
        with open(args.file) as f:
            flat = json.load(f)

        domain = import_domain(flat["synthetic_problem"]["problem"]["domain"])
        queries = [nested_to_smt(flat["synthetic_problem"]["problem"]["theory"])]
        support = domain.get_bounds()
        weights = Real(1)

    elif args.dialect == "wmi_generate_tree":
        queries = [read_smtlib(args.file + "_0.query")]
        support = read_smtlib(args.file + "_0.support")
        weights = read_smtlib(args.file + "_0.weights")
        variables = queries[0].get_free_variables() | support.get_free_variables() | weights.get_free_variables()
        domain = Domain.make(real_variable_bounds={v.symbol_name(): [-100, 100] for v in variables})

    elif args.dialect == "wmi_mspn":
        q_file, s_file, w_file = ("{}.{}".format(args.file, ext) for ext in ["query", "support", "weight"])
        queries = [] if not os.path.exists(q_file) else [read_smtlib(q_file)]
        support = read_smtlib(s_file)
        weights = read_smtlib(w_file)
        variables = support.get_free_variables() | weights.get_free_variables()  # type: Set[FNode]
        for query in queries:
            variables |= query.get_free_variables()
        # TODO Future work: detect bounds
        domain = Domain.make([v.symbol_name() for v in variables if v.get_type() == BOOL],
                             {v.symbol_name(): [-100, 100] for v in variables if v.get_type() == REAL})
    else:
        raise ValueError("Invalid conversion: {}".format(args.dialect))

    if args.task == "convert":
        json_file = args.json_file
        if json_file is None:
            json_file = args.file + ".converted.json"

        flat = {
            "domain": export_domain(domain, False),
            "queries": [smt_to_nested(query) for query in queries],
            "formula": smt_to_nested(support),
            "weights": smt_to_nested(weights)
        }

        with open(json_file, "w") as f:
            json.dump(flat, f)

    elif args.task == "volume":
        print(get_engine(args.engine, domain, support, weights).compute_volume())

    elif args.task == "compare":
        compare([get_engine(d, domain, support, weights) for d in args.engines])


if __name__ == "__main__":
    parse()