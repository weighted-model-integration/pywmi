import time

from pywmi import Domain, RejectionEngine, PyXaddEngine, PyXaddAlgebra
import pysmt.shortcuts as smt
from pywmi.domain import Density, FileDensity
from pywmi.engines.xsdd import FactorizedXsddEngine as FXSDD
from pywmi.engines.xsdd.vtrees.vtree import bami, balanced


def diabetes_example1():
    domain = Domain.make(["f0", "d0"], ["r0"], [(10, 45)])

    (
        f0,
        d0,
    ) = domain.get_bool_symbols()
    (r0,) = domain.get_real_symbols()

    support = (
        (f0 & (((d0 | ~d0) & ~(r0 <= 35)) | ((r0 <= 35) & (~d0))))
        | (~f0 & (d0 & (r0 <= 35)))
    ) & domain.get_bounds()
    # support_smaller = ((f0 & ((~(r0 <= 35)) | ~d0)) |
    #                    (~f0 & d0 & (r0 <= 35))) & \
    #                   domain.get_bounds()

    # support_smaller = ((f0 & ((~(r0 <= 35)) | ~d0))) & \
    #                   domain.get_bounds()

    support_smaller = (
        (f0 & ~(r0 <= 35) & ~d0) | (f0 & (r0 <= 35) & ~d0)
    ) & domain.get_bounds()

    weight_function = smt.Ite(f0, smt.Real(0.0001), smt.Real(0.00001)) * \
                      smt.Ite(d0, (r0/10)-1, 8-(r0/10)) * \
                      smt.Ite(r0 <= 35, -0.001*(r0-27)*(r0-27)+0.3, -0.001*(r0-27)*(r0-27)+0.3)
    #
    # weight_function_smaller = smt.Ite(f0, smt.Real(0.0001), smt.Real(0.00001)) * \
    #                           r0 *\
    #                           smt.Ite(r0 <= 35, -0.001*(r0)*(r0)+0.3, -0.001*(r0)*(r0)+0.3)
    weight_function_smaller = (
        smt.Real(0.00000001) * r0 * r0 * r0
    )  # * smt.Real(1000)  #<--- add this changes the result from 0.0 to 102
    density = Density(
        domain, support & domain.get_bounds(), weight_function
    )  # weight_function)
    query = d0

    startTime = time.time()
    rejection_engine = RejectionEngine(
        density.domain, density.support, density.weight, sample_count=1000000
    )

    vol1 = rejection_engine.compute_volume()
    result1 = rejection_engine.compute_probability(query)
    endTime = time.time()
    time1 = endTime - startTime

    startTime = time.time()
    xadd_engine = PyXaddEngine(density.domain, density.support, density.weight)
    vol2 = xadd_engine.compute_volume(add_bounds=False)
    result2 = xadd_engine.compute_probability(query)
    endTime = time.time()
    time2 = endTime - startTime
    # XsddEngine
    algebra = PyXaddAlgebra(reduce_strategy=PyXaddAlgebra.FULL_REDUCE)
    mfxsdd = FXSDD(
        density.domain,
        density.support,
        density.weight,
        vtree_strategy=balanced,
        algebra=algebra,
        ordered=False,
    )
    startTime = time.time()
    vol3 = mfxsdd.compute_volume(add_bounds=False)
    result3 = mfxsdd.compute_probability(query=query, add_bounds=False)
    endTime = time.time()
    time3 = endTime - startTime

    print(f"R1 {result1}, time1: {time1}")
    print(f"R2 {result2}, time2: {time2}")
    print(f"R3 {result3}, time3: {time3}")
    print("")
    print(f"Vol1 {vol1}, time1: {time1}")
    print(f"Vol2 {vol2}, time2: {time2}")
    print(f"Vol3 {vol3}, time3: {time3}")
    return result1, result2, time1, time2


if __name__ == "__main__":
    diabetes_example1()
