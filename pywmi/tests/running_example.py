from pywmi import XaddEngine, RejectionEngine, Domain, Density
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

# Create rejection-sampling based engine (no setup required)
rejection_engine = RejectionEngine(domain, support, weight_function, sample_count=100000)

print("Volume (Rejection):           ", rejection_engine.compute_volume())  # Compute the weighted model integral
print("Query probability (Rejection):", rejection_engine.compute_probability(query))  # Compute query probability

# Create XADD engine (mode resolve refers to the integration algorithm described in
# Kolb et al. Efficient symbolic integration for probabilistic inference. IJCAI 2018)
# !! Requires XADD solver to be setup (see above) !!
xadd_engine = XaddEngine(domain, support, weight_function, mode="resolve")

print("Volume (XADD):                ", xadd_engine.compute_volume())  # Compute the weighted model integral
print("Query probability (XADD):     ", xadd_engine.compute_probability(query))  # Compute query probability

# Wrap support and weight function (and optionally queries) in a density object
density = Density(domain, support, weight_function, [query])

# Density object can be saved to and loaded from files
filename = "my_density.json"
density.to_file(filename)  # Save to file
density = Density.from_file(filename)  # Load from file

# Compare engines from command line
# python -m pywmi my_density.json compare rej:n100000 xadd:mresolve  # Compute the weighted model integral
# python -m pywmi my_density.json compare rej:n100000 xadd:mresolve -q 0  # Compute query probability (query at index 0)

# Compute volumes and probabilities from command line
# You can provide multiple engines and the result of the first engine not to fail will be returned
# python -m pywmi my_density.json volume rej:n100000  # Compute weighted model integral
# python -m pywmi my_density.json prob rej:n100000  # Compute all query probabilities

# Plot 2-D support
# python -m pywmi my_density.json plot -o my_density.png