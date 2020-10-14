import sys
import os
import pathlib

file_path = pathlib.Path(__file__).parent.absolute()

include_dirs = [
    x[0]
    for x in os.walk(os.path.join(file_path, "build"))
    if "psilibrary" in x[0] and not x[0].endswith("psipy")
]

assert len(include_dirs) == 1
lib_dir = include_dirs[0]
lib_dir = os.path.join(file_path, lib_dir)


if lib_dir not in sys.path:
    sys.path.append(lib_dir)

import psipy

from . import psipy as psi

