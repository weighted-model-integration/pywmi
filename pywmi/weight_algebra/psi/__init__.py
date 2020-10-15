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

print(file_path)
if len(include_dirs) == 1:
    lib_dir = os.path.join(file_path, include_dirs[0])

    if lib_dir not in sys.path:
        sys.path.append(lib_dir)

    import psipy as psi
elif len(include_dirs) > 1:
    raise RuntimeError(
        "You have multiple libraries installed (multiple psilibrary files in the psi/build directory)"
    )
else:
    raise InstallError()
