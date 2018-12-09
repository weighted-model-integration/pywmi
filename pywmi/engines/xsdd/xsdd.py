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

import hal_problog.utils
from hal_problog.solver import SumOperator, InferenceSolver
from hal_problog.formula import LogicFormula


logger = logging.getLogger(__name__)


class XsddEngine(Engine, SMT2PL):
    def __init__(self, domain, support, weight, mode=None, timeout=None):
        Engine.__init__(self, domain, support, weight)
        SMT2PL.__init__(self, domain, support, weight)
        self.problog_program = hal_problog.utils.load_string(self.string_program)
        self.solver = InferenceSolverWMI(abe="psi")

        self.mode = mode
        self.timeout = timeout


    def call_wmi(self, queries=None, timeout=None, **kwdargs):
        lf_hal, _, _, _ = self.solver.ground(self.problog_program, queries=None, **kwdargs)
        lf = break_cycles(lf_hal, LogicFormula(**kwdargs))
        operator = SumOperator()
        semiring = SemiringWMIPSI(operator.get_neutral(), self.solver.abe)
        diagram = self.solver.compile_formula(lf, **kwdargs)
        dde = diagram.get_evaluator(semiring=semiring, **kwdargs)
        sdds = dde.get_sdds()


        return [1]


    def compute_volume(self, timeout=None):
        if timeout is None:
            timeout = self.timeout
        result = self.call_wmi(timeout=timeout)
        if result is None or len(result) == 0:
            return None
        else:
            return result[0]

    def compute_probabilities(self, queries):
        volume = self.compute_volume()
        return [volume for q in queries]


    def copy(self, support, weight):
        return XsddEngine(self.domain, support, weight, self.mode, self.timeout)


    def __str__(self):
        result = "sadd:m{}".format(self.mode)
        if self.timeout is not None:
            result += ":t{}".format(self.timeout)
        return result


class InferenceSolverWMI(InferenceSolver):
    def __init__(self, abe=None):
        InferenceSolver.__init__(self, abe)
