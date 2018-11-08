import argparse
import logging
import time
from typing import Any, List, Dict

import numpy as np
import tabulate
from pysmt.fnode import FNode
from typing import Optional

from .convert import Import
from .domain import import_density, export_density
from pywmi import Domain, RejectionEngine, PredicateAbstractionEngine, XaddEngine, Engine, plot

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
        options = parse_options(parts[1:], "mode", "timeout")
        return XaddEngine(domain, support, weight, **options)


def get_volume(engines, queries=None, print_status=None):
    # type: (List[Engine], Optional[List[FNode]], Optional[bool]) -> Optional[float]

    for engine in engines:
        if print_status:
            print("Trying engine: {: <64}".format(str(engine)), end="\r", flush=True)
        if queries is None:
            volume = engine.compute_volume()
        else:
            volume = engine.compute_probabilities(queries)
        if volume is not None:
            if print_status:
                print(" " * 80, end="\r", flush=True)
            return volume
    if print_status:
        print(" " * 80, end="\r", flush=True)
    return None


def compare(engines, query=None):
    def mean(sequence):
        if any(e is None for e in sequence):
            return None
        return sum(sequence) / len(sequence)

    def std(sequence):
        if any(e is None for e in sequence):
            return None
        return np.std(np.array(sequence))

    def error(_exact_volume, _volume):
        if _exact_volume is None or _volume is None:
            return "-"
        return "{:.4f}".format(abs(_volume - _exact_volume) / abs(_exact_volume) if _exact_volume != 0 else 0)

    def r_duration(_reference_time, _duration):
        if _reference_time is None:
            return "-"
        return "{:.2f}".format(_duration / _reference_time if _reference_time != 0 else 0)

    def d_string(_d):
        return "{:.2f}s".format(_d) if _d is not None else "-"

    def vol_string(_v):
        return "{:.4f}".format(_v) if _v is not None else "-"

    exact_volumes = []
    exact_durations = []
    delta = 10 ** -5

    header = ["Engine", "Time", "R Time", "Volume", "Error", "Std.Dev"]
    stats = []
    for i, engine in enumerate(engines):
        print("Running engine {} of {}: {: <70}".format(i + 1, len(engines), str(engine)), end="\r", flush=True)

        durations = []
        volumes = []

        for i in range(1 if engine.exact else 1):
            start_time = time.time()
            if query is None:
                volumes.append(engine.compute_volume())
            else:
                volumes.append(engine.compute_probability(query))
            durations.append(time.time() - start_time)

            if engine.exact and volumes[-1] is not None:
                exact_volumes.append((i, volumes[-1]))
                exact_durations.append((i, durations[-1]))

        stats.append([engine, mean(durations), mean(volumes), std(volumes)])

    disagree = False
    for i in range(len(exact_volumes) - 1):
        for j in range(i + 1, len(exact_volumes)):
            if abs(exact_volumes[i][1] - exact_volumes[j][1]) >\
                    delta * min(abs(exact_volumes[i][1]), abs(exact_volumes[j][1])):
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
    vp.add_argument("engines", help="One or more engines (later engines are used if earlier engines fail)", nargs="+")
    vp.add_argument("-s", "--status", help="Print current status", action="store_true")

    pp = task_parsers.add_parser("prob")
    pp.add_argument("engines", help="One or more engines (later engines are used if earlier engines fail)", nargs="+")
    pp.add_argument("-s", "--status", help="Print current status", action="store_true")

    cp = task_parsers.add_parser("convert")
    cp.add_argument("-o", "--json_file", help="The output path for the json file", default=None)

    compare_p = task_parsers.add_parser("compare")
    compare_p.add_argument("engines", help="The engines to compare (see engine input format)", nargs="+")
    compare_p.add_argument("-q", "--query_index", help="The query index to check", default=None, type=int)

    normalize_p = task_parsers.add_parser("normalize")
    normalize_p.add_argument("new_support", type=str, help="The new support")
    normalize_p.add_argument("output_path", type=str, help="Output path for normalized xadd")
    normalize_p.add_argument("-t", "--total", action="store_true", help="Dump total model instead of paths")

    plot_p = task_parsers.add_parser("plot")
    plot_p.add_argument("-o", "--output", type=str, help="Output path", default=None)
    plot_p.add_argument("-x", "--feat_x", type=str, help="Feature x", default=None)
    plot_p.add_argument("-y", "--feat_y", type=str, help="Feature y", default=None)
    plot_p.add_argument("-d", "--difference", type=str, help="Path to density to compute difference for", default=None)

    parser.add_argument("-d", "--dialect", default=None, type=str, help="The dialect to use for import")
    args = parser.parse_args()

    domain, support, weight, queries = Import.import_density(args.file, args.dialect)

    if args.task == "convert":
        json_file = args.json_file
        if json_file is None:
            json_file = args.file + ".converted.json"

        export_density(json_file, domain, support, weight, queries)

    elif args.task == "volume":
        print(get_volume([get_engine(d, domain, support, weight) for d in args.engines], print_status=args.status))

    elif args.task == "prob":
        print(get_volume([get_engine(d, domain, support, weight) for d in args.engines], queries, args.status))

    elif args.task == "compare":
        query = None
        if args.query_index is not None and args.query_index < len(queries):
            query = queries[args.query_index]
        compare([get_engine(d, domain, support, weight) for d in args.engines], query)

    elif args.task == "normalize":
        engine = XaddEngine(domain, support, weight, "original")
        engine.normalize(import_density(args.new_support)[2], args.output_path, not args.total)

    elif args.task == "plot":
        if args.output is not None and args.output == "*":
            output_file = args.file + ".png"
        else:
            output_file = args.output
        if args.difference:
            other = import_density(args.difference)
            plot.plot_formula(output_file, domain, (support & ~other[2] | ~support & other[2]), (args.feat_x, args.feat_y))
        else:
            plot.plot_formula(output_file, domain, support, (args.feat_x, args.feat_y))


if __name__ == "__main__":
    parse()
