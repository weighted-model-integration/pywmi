# pywmi ![build status](https://travis-ci.org/samuelkolb/pywmi.svg?branch=master)
## Installation

    pip install pywmi

pywmi offers various services and engines that require additional installation steps.

### SMT solvers
pywmi relies upon pysmt to interface with SMT solvers. If you want to benefit from functionality relying on SMT solvers
please install an SMT solver through the pysmt-install tool that comes as part of your pywmi installation.

    pysmt-install --z3
    
Make sure that when you use pywmi, the SMT solvers are on your path. The pysmt-install tool can show you the necessary
commands.

    pysmt-install --env

### XADD engine
The XADD engine performs WMI using XADDs as described in [Kolb et al., 2018](https://www.ijcai.org/proceedings/2018/698).
To use this engine you need [Java](https://www.oracle.com/technetwork/java/javase/downloads/index.html), [Gurobi](https://www.gurobi.com) and the xadd library JAR file.
The pywmi-install tool that comes with your pywmi installation can automatically download and install the JAR file,
however, you need to install Java and Gurobi manually. Once you did that, just call:

    pywmi-install xadd


### Latte
The Latte integration backend (as well as the predicate abstraction solver) require
[Latte](https://www.math.ucdavis.edu/~latte/software.php) to be installed. You can find the latest releases on their
[GitHub releases page](https://github.com/latte-int/latte/releases). You'll probably want the bundle: latte-integrale.

**Summary**
1. `wget "https://github.com/latte-int/latte/releases/download/version_1_7_5/latte-integrale-1.7.5.tar.gz"`
2. `tar -xvzf latte-integrale-1.7.5.tar.gz`
3. `cd latte-integrale-1.7.5`
4. `./configure`
5. `make`
