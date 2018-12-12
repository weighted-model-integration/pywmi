import logging
import os
import re
import subprocess
import sys
from typing import Optional, List

from pysmt.fnode import FNode
from pysmt.shortcuts import Real, TRUE

from pywmi.domain import TemporaryDensityFile
from pywmi.engine import Engine

from .smt2pl import SMT2PL
from .evaluator import SemiringWMIPSI


from problog.cycles import break_cycles
from problog.formula import LogicFormula

from hal_problog.utils import load_string
from hal_problog.solver import SumOperator, InferenceSolver


logger = logging.getLogger(__name__)


class XsddEngine(Engine, SMT2PL):
    def __init__(self, domain, support, weight, mode=None, timeout=None):
        Engine.__init__(self, domain, support, weight)
        SMT2PL.__init__(self, domain, support, weight)
        self.solver = InferenceSolverWMI(abe="psi")
        self.real_variables = domain.real_vars

        self.mode = mode
        self.timeout = timeout

    def __str__(self):
        result = "sadd:m{}".format(self.mode)
        if self.timeout is not None:
            result += ":t{}".format(self.timeout)
        return result



    def call_wmi(self, queries=None, timeout=None, **kwdargs):
        weights = []
        for q in queries:
            self.problog_program.add_smt_query(q)
            program = load_string(self.problog_program.string_program)

            lf_hal, _, _, _ = self.solver.ground(program, queries=None, **kwdargs)
            lf = break_cycles(lf_hal, LogicFormula(**kwdargs))
            operator = SumOperator()
            semiring = SemiringWMIPSI(operator.get_neutral(), self.solver.abe)
            diagram = self.solver.compile_formula(lf, **kwdargs)
            dde = diagram.get_evaluator(semiring=semiring, **kwdargs)
            sdds = dde.get_sdds()
            sdds = self.sort_sdds(sdds, self.worldweight)

            weight = self.calculate_weight(sdds, self.real_variables, semiring, dde, **kwdargs)
            weights.append(weight)
        return weights

    @staticmethod
    def sort_sdds(sdds, worldweight):
        sdds = sdds["qe"]
        n_queries = len(sdds)
        sdds_sorted = [{} for i in range(0,int(n_queries/2))]
        for s in sdds:
            if s.functor=="q":
                sdds_sorted[s.args[0].functor]["qe"]=sdds[s]
            else:
                sdds_sorted[s.args[0].functor]["e"]=sdds[s]
            sdds_sorted[s.args[0].functor]["ww"]=worldweight[s.args[0].functor]
        return sdds_sorted


    @staticmethod
    def calculate_weight(sdds, variables, semiring, dde, **kwdargs):
        wmi_e = semiring.zero().expression
        wmi_qe = semiring.zero().expression
        for query in sdds:
            ww = semiring.poly2expr(query["ww"])
            e_evaluated = dde.evaluate_sdd(query["e"], semiring, normalization=False, evaluation_last=False)
            qe_evaluated = dde.evaluate_sdd(query["qe"], semiring, normalization=False, evaluation_last=False)
            if e_evaluated:
                w_e = semiring.integrate(ww, e_evaluated, variables)
                wmi_e = semiring.algebra.add_simplify(wmi_e, w_e)
            if qe_evaluated:
                w_qe = semiring.integrate(ww, qe_evaluated, variables)
                wmi_qe = semiring.algebra.add_simplify(wmi_qe, w_qe)

        wmi = semiring.algebra.div_simplify(wmi_qe,wmi_e)
        return wmi


    def compute_volume(self, queries, timeout=None):
        if timeout is None:
            timeout = self.timeout
        result = self.call_wmi(queries, timeout=timeout)
        if result is None or len(result) == 0:
            return None
        else:
            return result[0]

    def compute_probabilities(self, queries):
        volumes = self.compute_volume(queries)
        return volumes



class InferenceSolverWMI(InferenceSolver):
    def __init__(self, abe=None):
        InferenceSolver.__init__(self, abe)
