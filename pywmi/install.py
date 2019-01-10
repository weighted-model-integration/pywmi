import argparse
import os
import shutil
import urllib.request


def install_xadd(upgrade=False):
    file_name = os.path.join(os.path.dirname(__file__), "engines", "xadd.jar")
    if not upgrade and os.path.exists(file_name):
        print("XADD solver already installed")
    else:
        url = "https://www.dropbox.com/s/e33axb83ftghrfb/xadd.jar?dl=1"
        with urllib.request.urlopen(url) as response, open(file_name, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)


def main():
    parser = argparse.ArgumentParser(description="Installation utility for install external requirements")
    parser.add_argument("solver", help="Specify the solver to install, options are: [xadd]")
    parser.add_argument("-f", "--force", action="store_true", help="Reinstall solver if it already exists")

    args = parser.parse_args()
    if args.solver == "xadd":
        install_xadd(args.force)
    else:
        print("Unknown solver {}".format(args.solver))


if __name__ == "__main__":
    main()
