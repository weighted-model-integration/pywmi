# pywmi [![Build Status](https://travis-ci.org/samuelkolb/pywmi.svg?branch=master)](https://travis-ci.org/samuelkolb/pywmi)
## Installation

    pip install pywmi

pywmi offers various services and engines that require additional installation steps.

### SMT solvers
pywmi relies upon pysmt to interface with SMT solvers. If you want to benefit from functionality relying on SMT solvers
please install an SMT solver through the pysmt-install tool that comes as part of your pywmi installation.

    pysmt-install --msat  # example to install mathsat, more solvers are available
    
For older versions of PySMT (older than version 0.8), you have to make sure that when you use pywmi, the SMT solvers are on your path.
The pysmt-install tool can show you the necessary commands.

    pysmt-install --env

### XADD engine
The XADD engine performs WMI using XADDs as described in [Kolb et al., 2018](https://www.ijcai.org/proceedings/2018/698).
To use this engine you need [Java](https://www.oracle.com/technetwork/java/javase/downloads/index.html), [Gurobi](https://www.gurobi.com) and the xadd library JAR file.
The pywmi-install tool that comes with your pywmi installation can automatically download and install the JAR file,
however, you need to install Java and Gurobi manually. Once you did that, just call:

    pywmi-install xadd
    pywmi-install xadd --force  # To download a new version


### Predicate abstraction engine
The predicate abstraction engine (short PA engine) uses MathSAT and Latte to solve WMI using predicate abstraction, as 
described in [Morettin et al., 2017](https://www.ijcai.org/proceedings/2017/0100.pdf).
In order to use the PA engine, you need to install the MathSAT SMT solver (see instructions above),
Latte (see instructions below) and the [wmipa library](https://github.com/unitn-sml/wmi-pa). You can use the
`pysmt-install` utility to download the library.

    pywmi-install pa
    pywmi-install pa --force  # To download a new version

**Manual installation**

You can also download or clone the library manually and add it to your `PYTHONPATH`
1. Download / clone the [wmipa library](https://github.com/unitn-sml/wmi-pa)
2. Add the directory containing the library to your `PYTHONPATH`

### Latte
The Latte integration backend as well as the predicate abstraction solver require
[Latte](https://www.math.ucdavis.edu/~latte/software.php) to be installed. You can find the latest releases on their
[GitHub releases page](https://github.com/latte-int/latte/releases). You'll probably want the bundle: latte-integrale.

**Summary**
1. `wget "https://github.com/latte-int/latte/releases/download/version_1_7_5/latte-integrale-1.7.5.tar.gz"`
2. `tar -xvzf latte-integrale-1.7.5.tar.gz`
3. `cd latte-integrale-1.7.5`
4. `./configure`
5. `make`


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
