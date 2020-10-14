import os
import sys
import subprocess


def get_system():
    system = sys.platform
    if system.lower().startswith("java"):
        system = "java"
    if system.startswith("linux"):
        system = "linux"
    elif system.startswith("win"):
        system = "windows"
    elif system.startswith("mac"):
        system = "darwin"
    return system


def make_files_executable():
    path = os.path.dirname(os.path.abspath(__file__))
    psipath = os.path.join(path, "psi")
    for f_in in os.listdir(psipath):
        subprocess.call(["chmod", "+x", os.path.join(psipath, f_in)])


def _build_psi():
    if get_system() == "windows":
        print("The PSI library is not yet available for Windows.")
        return

    path = os.path.dirname(os.path.abspath(__file__))

    lib_dir = os.path.abspath(os.path.join(path, os.uname()[0].lower()))
    lib_name = os.path.join(lib_dir, "libpsi")

    subprocess.call(
        "dmd -O -release -inline -boundscheck=off -J./library *.d -fPIC -lib -of={lib_name}".format(
            lib_name=lib_name,
        ),
        shell=True,
        cwd=os.path.join(path, "psi"),
    )


def build_psi():
    make_files_executable()
    _build_psi()


if __name__ == "__main__":
    build_psi()
