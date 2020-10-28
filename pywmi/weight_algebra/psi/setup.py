from __future__ import print_function

import os
import sys
import glob

from pyd.support import setup, Extension
import distutils


def get_system():
    system = sys.platform
    if system.lower().startswith("java"):
        system = "java"
    if system.startswith("linux"):
        system = "linux"
    elif system.startswith("win"):
        system = "windows"
    elif system.startswith("darwin"):
        system = "darwin"
    return system


def get_lib_build_dir():
    path = os.path.dirname(os.path.abspath(__file__))
    libDir = os.path.join(
        path,
        "build",
        "psilibrary-%s-%s"
        % (
            distutils.util.get_platform(),
            ".".join(str(v) for v in sys.version_info[:2]),
        ),
    )
    return libDir


def build_psipy(force=False):
    system = get_system()
    if system == "windows":
        print("The psipy library is not yet available for Windows.")
        return

    root_path = os.path.dirname(os.path.realpath(__file__))

    lib_dir = os.path.abspath(os.path.join(root_path, "psipy", system))
    lib_build_dir = get_lib_build_dir()

    filelist = glob.glob("{lib_build_dir}/*.so".format(lib_build_dir=lib_build_dir))
    if force and os.path.isdir(lib_build_dir):
        for f in filelist:
            os.remove(f)

    psipy_module = Extension(
        "psipy",
        sources=["psipy/psipy.d"],
        build_deimos=True,
        d_lump=True,
        include_dirs=["psipy/psi"],
        library_dirs=[lib_dir],
        libraries=["psi"],
    )

    filelist = glob.glob("{lib_build_dir}/*.so".format(lib_build_dir=lib_build_dir))
    if not filelist:
        setup(
            name="psipy",
            version="0.1",
            author="Pedro Zuidberg Dos Martires",
            ext_modules=[psipy_module],
            description="python wrapper for Psi",
            script_args=[
                "build",
                "--compiler=dmd",
                "--build-lib={}".format(lib_build_dir),
            ],
            packages=["psipy"],
        )


if __name__ == "__main__":
    args = sys.argv
    force = False
    if "--force" in args:
        force = True
    build_psipy(force=force)
    print("\n")
    print("psipy library is now available")
