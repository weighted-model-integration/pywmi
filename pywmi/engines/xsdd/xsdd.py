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
from .evaluator import SemiringWMIPSI, SemiringWMIPSIPint, SemiringStaticAnalysisWMI


from problog.cycles import break_cycles
from problog.formula import LogicFormula

from hal_problog.utils import load_string
from hal_problog.solver import SumOperator, InferenceSolver, InferenceSolverPINT


logger = logging.getLogger(__name__)


class XsddEngine(Engine, SMT2PL):
    def __init__(self, domain, support, weight, mode=None, timeout=None, pint=False):
        Engine.__init__(self, domain, support, weight)
        SMT2PL.__init__(self, domain, support, weight)
        if pint:
            self.solver = InferenceSolverWMIPint(abe="psi")
        else:
            self.solver = InferenceSolverWMI(abe="psi")

        self.real_variables = domain.real_vars
        self.pint = pint

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
            if self.pint:
                weight = self.calculate_weight_pint(lf, operator, **kwdargs)
            else:
                weight = self.calculate_weight(lf, operator, **kwdargs)

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


    def calculate_weight(self, lf, operator, **kwdargs):
        diagram = self.solver.compile_formula(lf, **kwdargs)
        semiring = SemiringWMIPSI(operator.get_neutral(), self.solver.abe)
        dde = diagram.get_evaluator(semiring=semiring, **kwdargs)
        sdds = dde.get_sdds()
        sdds = self.sort_sdds(sdds, self.worldweight)


        wmi_e = semiring.zero().expression
        wmi_qe = semiring.zero().expression
        for query in sdds:
            ww = semiring.poly2expr(query["ww"])
            e_evaluated = dde.evaluate_sdd(query["e"], semiring, normalization=False, evaluation_last=False)
            qe_evaluated = dde.evaluate_sdd(query["qe"], semiring, normalization=False, evaluation_last=False)
            if e_evaluated:
                w_e = semiring.integrate(ww, e_evaluated, self.real_variables)
                wmi_e = semiring.algebra.add_simplify(wmi_e, w_e)
            if qe_evaluated:
                w_qe = semiring.integrate(ww, qe_evaluated, self.real_variables)
                wmi_qe = semiring.algebra.add_simplify(wmi_qe, w_qe)

        wmi = semiring.algebra.div_simplify(wmi_qe,wmi_e)
        return wmi

    def calculate_weight_pint(self, lf, operator, **kwdargs):
        diagram = self.solver.compile_formula(lf, **kwdargs)
        #
        semiring_tag = SemiringStaticAnalysisWMI(operator.get_neutral(), self.solver.abe, **kwdargs)
        semiring = SemiringWMIPSIPint(operator.get_neutral(), self.solver.abe, **kwdargs)

        dde = diagram.get_evaluator(semiring=semiring, **kwdargs)
        sdds = dde.get_sdds()
        tags = self.solver.get_tags(sdds, semiring_tag, dde, **kwdargs)
        # sdds = self.sort_sdds(sdds, self.worldweight)
        #
        # wmi_e = semiring.zero().expression
        wmi_qe = semiring.zero().expression
        # for query in sdds:
        #     ww = semiring.poly2expr(query["ww"])
        #     e_tags = self.get_tags()
        #     e_evaluated = dde.evaluate_sdd(query["e"], semiring, normalization=False, evaluation_last=False)
        #     qe_evaluated = dde.evaluate_sdd(query["qe"], semiring, normalization=False, evaluation_last=False)
        #     if e_evaluated:
        #         w_e = semiring.integrate(ww, e_evaluated, self.real_variables)
        #         wmi_e = semiring.algebra.add_simplify(wmi_e, w_e)
        #     if qe_evaluated:
        #         w_qe = semiring.integrate(ww, qe_evaluated, self.real_variables)
        #         wmi_qe = semiring.algebra.add_simplify(wmi_qe, w_qe)
        #
        # wmi = semiring.algebra.div_simplify(wmi_qe,wmi_e)
        return wmi_qe
        return wmi

    # def get_tags(self, sdds, semiring_tag, dde, **kwdargs):
    #
    #     return ({},{})



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

class InferenceSolverWMIPint(InferenceSolverPINT):
    def __init__(self, abe=None, **kwdargs):
        InferenceSolverPINT.__init__(self, abe=abe, **kwdargs)
