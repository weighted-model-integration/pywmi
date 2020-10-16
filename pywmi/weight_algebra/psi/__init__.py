import sys
import os
import pathlib

from ...errors import InstallError


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


file_path = pathlib.Path(__file__).parent.absolute()
system = get_system()

include_dirs = [
    x[0]
    for x in os.walk(os.path.join(file_path, "build"))
    if "psilibrary" in x[0] and not x[0].endswith("psipy") and system in x[0]
]

print(file_path)
if len(include_dirs) == 1:
    lib_dir = os.path.join(file_path, include_dirs[0])

    if lib_dir not in sys.path:
        sys.path.append(lib_dir)

    try:
        import psipy as psi
    except ImportError:
        raise InstallError()

elif len(include_dirs) > 1:
    raise RuntimeError(
        "You have multiple libraries installed (multiple psilibrary files in the psi/build directory)"
    )
else:
    raise InstallError()
