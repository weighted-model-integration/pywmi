import time

from pywmi import Domain, RejectionEngine, PyXaddEngine, PyXaddAlgebra
import pysmt.shortcuts as smt
from pywmi.domain import Density, FileDensity
from pywmi.engines.xsdd import XsddEngine as FXSDD


def diabetes_example1():
    domain = Domain.make(["f0", "d0"], ["b0"], [(10, 45)])

    f0, d0, = domain.get_bool_symbols()
    b0, = domain.get_real_symbols()

    support = ((f0 & (((d0 | ~d0) & ~(b0 <= 35)) | ((b0 <= 35) & (~d0)))) | (~f0 & (d0 & (b0 <= 35)))) & domain.get_bounds()
    support_smaller = ((f0 & ((~(b0 <= 35)) | ~d0)) |
                       (~f0 & d0 & (b0 <= 35))) & \
                      domain.get_bounds()
    support_smaller = ((f0 & ((~(b0 <= 35)) | ~d0))) & \
                      domain.get_bounds()
    support_smaller = ((f0 & ~(b0 <= 35) & ~d0) | (f0 & (b0 <= 35) & ~d0)) & \
                      domain.get_bounds()
    weight_function = smt.Ite(f0, smt.Real(0.0001), smt.Real(0.00001)) * \
                      smt.Ite(d0, (b0/10)-1, 8-(b0/10)) * \
                      smt.Ite(b0 <= 35, -0.001*(b0-27)*(b0-27)+0.3, -0.001*(b0-27)*(b0-27)+0.3)

    weight_function_smaller = smt.Ite(f0, smt.Real(0.0001), smt.Real(0.00001)) * \
                              b0 *\
                              smt.Ite(b0 <= 35, -0.001*(b0)*(b0)+0.3, -0.001*(b0)*(b0)+0.3)
    weight_function_smaller = smt.Ite(f0, smt.Real(0.0001), smt.Real(0.00001)) * \
                              b0 *\
                              smt.Ite(b0 <= 35, -0.002*(b0)*(b0)+0.4, -0.001*(b0)*(b0)+0.3)
    density = Density(domain, support_smaller & domain.get_bounds(), weight_function_smaller) #weight_function)
    query = d0

    startTime = time.time()
    rejection_engine = RejectionEngine(domain, support, density.weight, sample_count=1000000)

    vol1 = rejection_engine.compute_volume()
    result1 = rejection_engine.compute_probability(query)
    endTime = time.time()
    time1 = endTime-startTime

    startTime = time.time()
    xadd_engine = PyXaddEngine(density.domain, density.support, density.weight)
    vol2 = xadd_engine.compute_volume(add_bounds=False)
    result2 = xadd_engine.compute_probability(query)
    endTime = time.time()
    time2 = endTime-startTime
    # XsddEngine
    algebra = PyXaddAlgebra(reduce_strategy=PyXaddAlgebra.FULL_REDUCE)
    mfxsdd = FXSDD(density.domain, density.support, density.weight, algebra=algebra, ordered=False, factorized=True)
    startTime = time.time()
    vol3 = mfxsdd.compute_volume(add_bounds=False)
    result3 = mfxsdd.compute_probability(query=query, add_bounds=False)
    endTime = time.time()
    time3 = endTime-startTime

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
