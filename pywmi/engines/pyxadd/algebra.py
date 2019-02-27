from .operation import Summation, Multiplication
from .resolve import ResolveIntegrator
from .core import Diagram, Pool
from .decision import Decision
from pywmi import Domain
from pywmi.engines.algebraic_backend import AlgebraBackend, IntegrationBackend, PSIAlgebra
from pysmt.fnode import FNode


class PyXaddAlgebra(AlgebraBackend, IntegrationBackend):
    FULL_REDUCE = (True, ResolveIntegrator.FULL_REDUCE)
    ONLY_INTEGRATION_REDUCE = (False, ResolveIntegrator.FULL_REDUCE)
    ONLY_INIT_INTEGRATION_REDUCE = (False, ResolveIntegrator.NO_SUM_PRODUCT_REDUCE)
    ONLY_WALKING_REDUCE = (True, ResolveIntegrator.NO_REDUCE)
    NO_REDUCE = (False, ResolveIntegrator.NO_REDUCE)

    def __init__(self, pool=None, symbolic_backend=None, reduce_strategy=None):
        self.symbolic_backend = symbolic_backend or PSIAlgebra()
        self.pool = pool or Pool(algebra=self.symbolic_backend)
        self.reduce_strategy = reduce_strategy or self.FULL_REDUCE
        AlgebraBackend.__init__(self)
        IntegrationBackend.__init__(self, self.symbolic_backend.exact)

    def symbol(self, name: str) -> int:
        return self.pool.terminal(self.symbolic_backend.symbol(name))

    def real(self, float_constant: float) -> int:
        return self.pool.terminal(self.symbolic_backend.real(float_constant))

    def to_float(self, real_value: int) -> float:
        node = self.pool.get_node(real_value)
        assert node.is_terminal()
        return self.pool.algebra.to_float(node.expression)

    def integrate(self, domain: Domain, expression: int, variables=None) -> int:
        result = expression
        integrator = ResolveIntegrator(self.pool, reduce_strategy=self.reduce_strategy[1])
        for v in (variables or domain.variables):
            result = integrator.integrate(result, domain.get_symbol(v))
        return result

    def zero(self) -> int:
        return self.pool.zero_id

    def one(self) -> int:
        return self.pool.one_id

    def times(self, a: int, b: int) -> int:
        result_id = self.pool.apply(Multiplication, a, b)
        if not self.reduce_strategy[0]:
            return result_id
        return self.pool.diagram(result_id).reduce().root_id

    def plus(self, a: int, b: int) -> int:
        result_id = self.pool.apply(Summation, a, b)
        if not self.reduce_strategy[0]:
            return result_id
        return self.pool.diagram(result_id).reduce().root_id

    def less_than(self, a: int, b: int) -> int:
        raise NotImplementedError()

    def less_than_equal(self, a: int, b: int) -> int:
        raise NotImplementedError()

    def greater_than(self, a: int, b: int) -> int:
        raise NotImplementedError()

    def greater_than_equal(self, a: int, b: int) -> int:
        raise NotImplementedError()

    def parse_condition(self, condition: FNode):
        return self.pool.bool_test(Decision(condition))
