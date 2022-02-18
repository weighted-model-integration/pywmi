# pywmi

This is the `pywmi` package. It offers a unified and high-level API to a variety of weighted model integration solvers.

If you use the `pywmi` library in your own research please cite us as follows:

```
@inproceedings{kolb2019pywmi,
  title     = {The pywmi Framework and Toolbox for Probabilistic Inference using Weighted Model Integration},
  author    = {Kolb, Samuel and Morettin, Paolo  and Zuidberg Dos Martires, Pedro and Sommavilla, Francesco and Passerini, Andrea and Sebastiani, Roberto and De Raedt, Luc},
  booktitle = {Proceedings of the Twenty-Eighth International Joint Conference on
               Artificial Intelligence, {IJCAI-19}},
  publisher = {International Joint Conferences on Artificial Intelligence Organization},             
  pages     = {6530--6532},
  year      = {2019},
}
```

<br/><br/>


## Installation

    pip install pywmi

pywmi offers various services and engines that require additional installation steps.  pywmi includes a helper utility
`pywmi-install` to help installing components required by various engines.  To see an overview of the solvers, the
components they depend on and wether or not they are installed run:

    pywmi-install --list

<br/><br/>

### <ins>SMT solvers</ins>
pywmi relies upon pysmt to interface with SMT solvers. If you want to benefit from functionality relying on SMT solvers
please install an SMT solver through the pysmt-install tool that comes as part of your pywmi installation.

    pysmt-install --msat  # example to install mathsat, more solvers are available

<br/><br/>

### <ins>PyXADD engine</ins>
pywmi includes a native Python implementation of XADDs (a sublibrary called pyxadd).  The PyXaddEngine uses pyxadd to
perform WMI inference.  To use the PyXaddEngine, you need to install an SMT solver (see instructions above) and
**optionally** the symbolic computation library PSI (see instructions below).

<br/><br/>

### <ins>XADD engine</ins>
The XADD engine performs WMI using XADDs as described in [Kolb et al., 2018](https://www.ijcai.org/proceedings/2018/698).
To use this engine you need [Java](https://www.oracle.com/technetwork/java/javase/downloads/index.html), [Gurobi](https://www.gurobi.com) and the xadd library JAR file.
The pywmi-install tool that comes with your pywmi installation can automatically download and install the JAR file,
however, you need to install Java and Gurobi manually. Once you did that, just call:

    pywmi-install xadd
    pywmi-install xadd --force  # To download a new version

<br/><br/>

### <ins>Predicate abstraction engine</ins>
The predicate abstraction engine (short PA engine) uses MathSAT and Latte to solve WMI using predicate abstraction, as 
described in [Morettin et al., 2017](https://www.ijcai.org/proceedings/2017/0100.pdf) and [Morettin et al., 2019](https://www.sciencedirect.com/science/article/abs/pii/S0004370219301213).
In order to use the PA engine, you need to install the MathSAT SMT solver (see instructions above) and Latte (see instructions below).

<br/><br/>

### <ins>MPWMI engine</ins>
The MPWMI engine performs WMI using the message-passing scheme described in [Zeng et al., 2020](https://arxiv.org/pdf/2003.00126.pdf).
The solver works exclusively with problems having a dependency (aka primal) graph with treewidth 1 and per-literal weights, i.e.:

    weight = Times(Ite(lit_1, wlit_1, Real(1)), ... , Ite(lit_k, wlit_k, Real(1)))

**Installation**
1. `git clone https://github.com/UCLA-StarAI/mpwmi`
2. `pip install -e mpwmi/`

  
  <br/><br/>

### <ins>PSI support</ins>

By default `pywmi`  uses [Sympy](https://www.sympy.org/en/index.html) as a symbolic computer algebra backend. For an enhanced performance `pywmi` does also provide support to using the PSi[PSI](https://psisolver.org/) solver.

**Installation**

Make sure you have your Python virtual environment active.

1. You need to install the D language runtime -- [PSI](https://psisolver.org/) is written in D (https://dlang.org/).  
  
   On **Mac** you might need to install `gnupg` to verify the installation, e.g., through `brew install gnupg` --
be aware that this might install a lot of requirements.
The alternative way to install the D runtime through `brew install dmd` is currently broken.

       curl -fsS https://dlang.org/install.sh | bash -s dmd -p PATH/TO/WHERE/YOU/WANT/DLANG/

2. Now, make sure that the D runtime is in your path.  
    * Either you use the follwong command  

          source PATH/TO/WHERE/YOU/WANT/DLANG/dmd-2.0**.*/activate

    * Or by adding the following lines to your .bashr file, for instance:
        
            #export PATH=$HOME/software/dlang/dmd-2.0**.*/linux/bin64:$PATH
            #export LD_LIBRARY_PATH=$HOME/software/dlang/dmd-2.0**.*/linux/lib64:$LD_LIBRARY_PATH


3. Next, you need to install Python bindings for D (make sure that you have activated your Python virtual environment).

```
cd pywmi/pywmi/weight_algebra/psi
python build_psi.py
python setup.py install --force
```
This will build python bindings to the symbolic inference engine of PSI, which can be used in in the backend.


<!-- 2. Next, you need to install Python bindings for D (make sure that you have activated your Python virtual environment).
```
git clone https://github.com/ariovistus/pyd.git
cd pyd
python setup.py install
```

Finally, you need install psipy (Python bindings for the PSI library).  Navigate to your pywmi home folder, then run:

```
cd pywmi/weight_algebra/psi/psipy
python build_psi.py
cd ..
python setup.py install 
``` -->


<br/><br/>

### <ins>Latte<ins/>
The Latte integration backend as well as the predicate abstraction solver require
[Latte](https://www.math.ucdavis.edu/~latte/software.php) to be installed. You can find the latest releases on their
[GitHub releases page](https://github.com/latte-int/latte/releases). You'll probably want the bundle: latte-integrale.

**Summary**
1. `wget "https://github.com/latte-int/latte/releases/download/version_1_7_5/latte-integrale-1.7.5.tar.gz"`
2. `tar -xvzf latte-integrale-1.7.5.tar.gz`
3. `cd latte-integrale-1.7.5`
4. `./configure`
5. `make`

Then, include the binaries folder to your `PATH` variable.

<br/><br/>

<br/><br/>

## Usage
### Calling pywmi

**Setup density and query**

    import pysmt.shortcuts as smt
    
    # Create a "domain" with boolean variables a and b and real variables x, y (both between 0 and 1)
    domain = Domain.make(["a", "b"], ["x", "y"], [(0, 1), (0, 1)])
    
    a, b = domain.get_bool_symbols()  # Get PySMT symbols for the boolean variables
    x, y = domain.get_real_symbols()  # Get PySMT variables for the continuous variables
    
    # Create support
    support = (a | b) & (~a | ~b) & (x <= y) & domain.get_bounds()
    
    # Create weight function (PySMT requires constants to be wrapped, e.g., smt.Real(0.2))
    weight_function = smt.Ite(a, smt.Real(0.2), smt.Real(0.8)) * (smt.Ite(x <= 0.5, smt.Real(0.2), 0.2 + y) + smt.Real(0.1))
    
    # Create query
    query = x <= y / 2
    
**Use engine to perform inference**

    # Create rejection-sampling based engine (no setup required)
    rejection_engine = RejectionEngine(domain, support, weight_function, sample_count=100000)
    
    print("Volume (Rejection):           ", rejection_engine.compute_volume())  # Compute the weighted model integral
    print("Query probability (Rejection):", rejection_engine.compute_probability(query))  # Compute query probability
    
 **Use XADD engine (make sure you have installed the prerequisites)**
 
    # Create XADD engine (mode resolve refers to the integration algorithm described in
    # Kolb et al. Efficient symbolic integration for probabilistic inference. IJCAI 2018)
    # !! Requires XADD solver to be setup (see above) !!
    xadd_engine = XaddEngine(domain, support, weight_function, mode="resolve")
    
    print("Volume (XADD):                ", xadd_engine.compute_volume())  # Compute the weighted model integral
    print("Query probability (XADD):     ", xadd_engine.compute_probability(query))  # Compute query probability

**Generating uniform samples and their labels**

    from pywmi.sample import uniform
    # n: Required number of samples
    # domain, support: Domain and support defined as above
    samples = uniform(domain, n)
    labels = evaluate(samples, support, samples)

**Generating weighted positive samples**

    from pywmi.sample import positive
    # n: Required number of samples
    # domain, support, weight: Defining the density as above
    # Optional:
    #   sample_pool_size: The number of uniformly sampled positive samples to weight and select the samples from
    #   sample_count: The number of samples to draw initially, from which to build the positive pool
    #   max_samples: The maximum number of uniformly sampled samples (positive or negative) to generate before failing
    #                => If max_samples is exceeded a SamplingError will be raised
    samples, positive_ratio = positive(n, domain, support, weight)
    
**Handle densities and write to files**

    # Wrap support and weight function (and optionally queries) in a density object
    density = Density(domain, support, weight_function, [query])
    
    # Density object can be saved to and loaded from files
    filename = "my_density.json"
    density.to_file(filename)  # Save to file
    density = Density.from_file(filename)  # Load from file

**Work from command line**

    # Compare engines from command line
    python -m pywmi my_density.json compare rej:n100000 xadd:mresolve  # Compute the weighted model integral
    python -m pywmi my_density.json compare rej:n100000 xadd:mresolve -q 0  # Compute query probability (query at index 0)
    
    # Compute volumes and probabilities from command line
    # You can provide multiple engines and the result of the first engine not to fail will be returned
    python -m pywmi my_density.json volume rej:n100000  # Compute weighted model integral
    python -m pywmi my_density.json prob rej:n100000  # Compute all query probabilities
    
    # Plot 2-D support
    python -m pywmi my_density.json plot -o my_density.png
    
Find the complete running example in [pywmi/tests/running_example.py](pywmi/tests/running_example.py)
