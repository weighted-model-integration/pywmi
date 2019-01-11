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

### XSDD engine
WMI using XSDD inference is also supported by pywmi. To use the XSDD engine you need to install
[HAL-ProbLog](https://bitbucket.org/pedrozudo/hal_problog) by following the instructions provided in the README file.

**Summary**
1. Install the [dmd compiler v2.078.3](http://downloads.dlang.org/releases/2.x/2.078.3/)
2. `git clone https://github.com/ariovistus/pyd.git`
3. `cd pyd`
4. `python setup.py install`
5. `cd ../`
6. `git clone --recursive https://github.com/ML-KULeuven/psipy.git`
7. `cd psypi`
8. `python psipy/build_psi.py`
9. `python setup.py install`
10. Add the psi library to your path (command printed during the previous step)
11. `cd ../`
12. `git clone https://bitbucket.org/pedrozudo/hal_problog.git`
13. `cd hal_problog`
14. `python setup.py install`

Take care that your code does not run in the same directory as the one you cloned the libraries, as they will pollute
your namespace.