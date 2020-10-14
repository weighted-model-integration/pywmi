import sys
import os
import pathlib

from ...errors import InstallError

file_path = pathlib.Path(__file__).parent.absolute()

include_dirs = [
    x[0]
    for x in os.walk(os.path.join(file_path, "build"))
    if "psilibrary" in x[0] and not x[0].endswith("psipy")
]

if len(include_dirs) == 1:
    lib_dir = os.path.join(file_path, include_dirs[0])

    if lib_dir not in sys.path:
        sys.path.append(lib_dir)

    from . import psipy as psi
else:
    raise InstallError()
