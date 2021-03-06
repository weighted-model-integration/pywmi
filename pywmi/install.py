import argparse
import os
import shutil
import urllib.request
from traceback import print_exc

import tabulate
from pysmt.exceptions import NoSolverAvailableError
from pysmt.shortcuts import Solver

from pywmi.errors import InstallError


def check_installation_pysdd():
    try:
        import pysdd

        return True
    except ImportError:
        return False


def check_installation_psi():
    try:
        from pywmi.weight_algebra.psi import psi

        return True
    except InstallError:
        return False


def check_installation_smt_solver():
    try:
        with Solver():
            return True
    except NoSolverAvailableError:
        return False


def check_installation_gurobi():
    if not shutil.which("gurobi"):
        return False
    return True


def check_installation_latte():
    if not shutil.which("integrate"):
        return False
    return True


def check_installation_xadd_jar():
    file_name = os.path.join(os.path.dirname(__file__), "engines", "xadd.jar")
    return os.path.exists(file_name)


def check_installation_pyxadd():
    return check_installation_psi() and check_installation_smt_solver()


def check_installation_pa():
    return check_installation_latte() and check_installation_smt_solver()


def check_installation_xadd():
    return check_installation_xadd_jar() and check_installation_gurobi()


def install_xadd(upgrade=False, remove=False):
    file_name = os.path.join(os.path.dirname(__file__), "engines", "xadd.jar")
    if remove:
        if os.path.exists(file_name):
            os.unlink(file_name)
            print("Removed XADD solver at {}".format(file_name))
        else:
            print("XADD solver is not installed")

    if not upgrade and os.path.exists(file_name):
        print("XADD solver already installed")
    else:
        print("Downloading JAR file to {}".format(file_name))
        url = "https://www.dropbox.com/s/e33axb83ftghrfb/xadd.jar?dl=1"
        with urllib.request.urlopen(url) as response, open(file_name, "wb") as out_file:
            shutil.copyfileobj(response, out_file)


def main():
    parser = argparse.ArgumentParser(
        description="Installation utility for install external requirements"
    )
    parser.add_argument(
        "solver", nargs="?", help="Specify the solver to install, options are: [xadd]"
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Reinstall solver if it already exists",
    )
    parser.add_argument("-r", "--remove", action="store_true", help="Remove solver")
    parser.add_argument(
        "-l", "--list", action="store_true", help="List available solvers"
    )

    args = parser.parse_args()
    if args.solver is None and args.list:
        solvers = [
            ("pa", ["Latte", "SMT Solver"]),
            ("pyxadd", ["SMT Solver"]),
            ("XADD", ["Gurobi", "SMT Solver", "XADD JAR"]),
            ("XSDD", ["PSI"]),
        ]

        components = {
            "PSI": check_installation_psi(),
            "Latte": check_installation_latte(),
            "SMT Solver": check_installation_smt_solver(),
            "Gurobi": check_installation_gurobi(),
            "XADD JAR": check_installation_xadd_jar(),
        }

        print(
            tabulate.tabulate(
                [
                    [
                        "{} ({})".format(
                            solver,
                            "v" if all(components[c] for c in dependencies) else "x",
                        )
                    ]
                    + [
                        ("v" if components[component] else "x")
                        if component in dependencies
                        else "-"
                        for component in components
                    ]
                    for solver, dependencies in solvers
                ],
                headers=["Solver \\ Component"]
                + [
                    "{} ({})".format(c, "v" if r else "x")
                    for c, r in components.items()
                ],
            )
        )
    elif args.solver == "xadd":
        install_xadd(args.force, args.remove)
    else:
        print("Unknown solver {}".format(args.solver))


if __name__ == "__main__":
    main()
