import logging
from collections import OrderedDict
from pysmt import shortcuts as smt


# from pywmi.domain import TemporaryDensityFile
from pywmi.engine import Engine

from problog.cycles import break_cycles
from problog.formula import LogicFormula

from hal_problog.utils import load_string
from hal_problog.solver import SumOperator, InferenceSolver, InferenceSolverPINT
from hal_problog.formula import LogicFormulaHAL

from .smt2pl import SMT2PL
from .evaluator import SemiringWMIPSI, SemiringWMIPSIPint, SemiringStaticAnalysisWMI, poly2expr


import psipy


logger = logging.getLogger(__name__)


class XsddEngine(Engine, SMT2PL):
    def __init__(self, domain, support, weight, mode=None, timeout=None, pint=False, collapse=False, repeated=False):
        Engine.__init__(self, domain, support, weight)
        SMT2PL.__init__(self, domain, support, weight)
        if pint:
            self.solver = InferenceSolverWMIPint(abe="psi")
        else:
            self.solver = InferenceSolverWMI(abe="psi")

        self.real_variables = domain.real_vars
        self.pint = pint
        self.collapse = collapse
        self.repeated = repeated

        self.mode = mode
        self.timeout = timeout

    def __str__(self):
        result = "sadd:m{}".format(self.mode)
        if self.timeout is not None:
            result += ":t{}".format(self.timeout)
        return result


    @staticmethod
    def check_for_repeated(queries):
        free_variables = [smt.get_free_variables(q)  for q in queries]
        repeated = True
        for v in free_variables[0]:
            repeated =  repeated and not v.is_literal()
        repeated = repeated and len(set(free_variables)) <= 1
        return repeated, [smt.serialize(v) for v in free_variables[0]]

    def call_wmi(self, queries=None, timeout=None, **kwdargs):
        queries = queries or []
        if self.repeated:
            self.repeated, free_variables = self.check_for_repeated(queries)
            if self.repeated:
                self.free_variables = free_variables

        for q in queries:
            self.problog_program.add_smt_query(q, queries.index(q))

        program = load_string(self.problog_program.string_program)

        lf_hal, _, _, _ = self.solver.ground(program, queries=None, **kwdargs)
        lf = break_cycles(lf_hal, LogicFormulaHAL(**kwdargs))
        operator = SumOperator()


        if self.pint:
            weights = self.calculate_weight_pint(lf, operator, **kwdargs)
        elif self.collapse:
            weights = self.calculate_weight_collapse(lf, operator, **kwdargs)
        else:
            weights = self.calculate_weight(lf, operator, **kwdargs)

        return weights


    @staticmethod
    def sort_sdds(sdds, worldweight):
        sdds_sorted = {"support": {}, "queries": {}, "ww": {}}
        for s in sdds:
            if s.functor=="q":
                sdds_sorted["queries"][s.args[0].functor]=sdds[s]


            elif s.functor=="support":
                sdds_sorted["support"][s.args[0].functor]=sdds[s]
                sdds_sorted["ww"][s.args[0].functor]=worldweight[s.args[0].functor]


        return sdds_sorted


    def get_sdds(self, dde):#node
        result = {}
        for query, node in dde.formula.queries():
            if node is dde.formula.FALSE:
                result[query] = dde.formula.FALSE
            else:
                query_def_inode = dde.formula.get_inode(node)
                result[query] = query_def_inode
        return result


    def calculate_weight(self, lf, operator, **kwdargs):
        diagram = self.solver.compile_formula(lf, **kwdargs)
        semiring = SemiringWMIPSI(operator.get_neutral(), self.solver.abe)
        dde = diagram.get_evaluator(semiring=semiring, **kwdargs)
        sdd_manager = dde._get_manager()
        sdds = self.get_sdds(dde)

        sdds = self.sort_sdds(sdds, self.worldweight)

        results = {}
        if self.repeated:
            partially_integrated_support = []
            wmi_e = psipy.S("0")
            for w in sdds["support"]:
                ww = poly2expr(sdds["ww"][w])
                support = dde.evaluate_sdd(sdds["support"][w], semiring, normalization=False, evaluation_last=False)
                int_variables = [v for v in self.real_variables if not v in self.free_variables]
                support = psipy.mul(ww, support.expression)
                support = psipy.integrate(int_variables, support)
                partially_integrated_support.append(support)
                int_variables = [v for v in self.real_variables if v in self.free_variables]
                support = psipy.integrate(int_variables, support)
                wmi_e = psipy.add(wmi_e, support)
                wmi_e = psipy.simplify(wmi_e)

            int_variables = [v for v in self.real_variables if v in self.free_variables]
            for q in sdds["queries"]:
                wmi_qe = psipy.S("0")
                w_qe = dde.evaluate_sdd(sdds["queries"][q], semiring, normalization=False, evaluation_last=False).expression
                for s in partially_integrated_support:
                    w_qe_sub = psipy.mul(w_qe, s)
                    w_qe_sub = psipy.integrate(int_variables, w_qe_sub)
                    wmi_qe = psipy.add(wmi_qe, w_qe_sub)
                results.append((wmi_qe,wmi_e))
            #need to do this because did not use OrderedDict (idiot)
            results = [results[index] for index in range(0,len(results))]
            return results
        else:
            wmi_e = psipy.S("0")
            for w in sdds["support"]:
                ww = poly2expr(sdds["ww"][w])
                e_evaluated = dde.evaluate_sdd(sdds["support"][w], semiring, normalization=False, evaluation_last=False)
                if e_evaluated:
                    w_e = semiring.integrate(ww, e_evaluated, self.real_variables)
                    wmi_e = semiring.algebra.add_simplify(wmi_e, w_e)

            for k_q, v_q in sdds["queries"].items():
                qe_sdds = {k_s:sdd_manager.conjoin(v_q,v_s) for k_s,v_s in sdds["support"].items()}
                wmi_qe = psipy.S("0")

                for w in sdds["support"]:
                    ww = poly2expr(sdds["ww"][w])
                    qe_evaluated = dde.evaluate_sdd(qe_sdds[w], semiring, normalization=False, evaluation_last=False)
                    if qe_evaluated:
                        # print(qe_evaluated)
                        w_qe = semiring.integrate(ww, qe_evaluated, self.real_variables)
                        wmi_qe = semiring.algebra.add_simplify(wmi_qe, w_qe)

                results[k_q] = (wmi_qe,wmi_e)
            #need to do this because did not use OrderedDict (idiot)
            results = [results[index] for index in range(0,len(results))]
            return results





    def calculate_weight_collapse(self, lf, operator, **kwdargs):
        diagram = self.solver.compile_formula(lf, **kwdargs)
        semiring = SemiringWMIPSI(operator.get_neutral(), self.solver.abe)
        dde = diagram.get_evaluator(semiring=semiring, **kwdargs)
        sdd_manager = dde._get_manager()

        sdds = self.get_sdds(dde)
        sdds = self.sort_sdds(sdds, self.worldweight)


        e_interval2weight = {}
        for w in sdds["support"]:
            ww = poly2expr(sdds["ww"][w])
            e_evaluated = dde.evaluate_sdd(sdds["support"][w], semiring, normalization=False, evaluation_last=False)
            if e_evaluated:
                e_evaluated_str = psipy.toString(e_evaluated.expression)

                if e_evaluated_str in e_interval2weight:
                    e_interval2weight[e_evaluated_str][1] = \
                        psipy.simplify(psipy.add(e_interval2weight[e_evaluated_str][1] , ww))
                else:
                    e_interval2weight[e_evaluated_str] = [e_evaluated, ww]
        wmi_e = psipy.S("0")
        for i in e_interval2weight:
            w_e = semiring.integrate(e_interval2weight[i][1], e_interval2weight[i][0], self.real_variables)
            wmi_e = semiring.algebra.add_simplify(wmi_e, w_e)


        results = {}
        for k_q, v_q in sdds["queries"].items():
            qe_sdds = {k_s:sdd_manager.conjoin(v_q,v_s) for k_s,v_s in sdds["support"].items()}
            qe_interval2weight = {}
            for w in sdds["support"]:
                ww = poly2expr(sdds["ww"][w])
                qe_evaluated = dde.evaluate_sdd(qe_sdds[w], semiring, normalization=False, evaluation_last=False)
                if qe_evaluated:
                    qe_evaluated_str = psipy.toString(qe_evaluated.expression)

                    if qe_evaluated_str in qe_interval2weight:
                        qe_interval2weight[qe_evaluated_str][1] = \
                            psipy.simplify(psipy.add(qe_interval2weight[qe_evaluated_str][1] , ww))
                    else:
                        qe_interval2weight[qe_evaluated_str] = [qe_evaluated, ww]

            wmi_qe = psipy.S("0")
            for i in qe_interval2weight:
                w_qe = semiring.integrate(qe_interval2weight[i][1], qe_interval2weight[i][0], self.real_variables)
                wmi_qe = semiring.algebra.add_simplify(wmi_qe, w_qe)
            results[k_q] = (wmi_qe,wmi_e)

        #need to do this because did not use OrderedDict (idiot)
        results = [results[index] for index in range(0,len(results))]
        return results





    def calculate_weight_pint(self, lf, operator, **kwdargs):
        diagram = self.solver.compile_formula(lf, **kwdargs)
        #
        semiring_tag = SemiringStaticAnalysisWMI(operator.get_neutral(), self.solver.abe, **kwdargs)
        semiring = SemiringWMIPSIPint(operator.get_neutral(), self.solver.abe, **kwdargs)

        dde = diagram.get_evaluator(semiring=semiring, **kwdargs)
        sdd_manager = dde._get_manager()

        sdds = self.get_sdds(dde)
        sdds = self.sort_sdds(sdds, self.worldweight)

        wmi_e = psipy.S("0")
        for w in sdds["support"]:
            tags = self.solver.get_tags(sdds["support"][w], semiring_tag, dde, **kwdargs)

            semiring.ww = poly2expr(sdds["ww"][w])
            semiring.tags = tags
            semiring.normalization = True
            e_evaluated = dde.evaluate_sdd(sdds["support"][w], semiring, normalization=True, evaluation_last=False)
            wmi_e = semiring.algebra.add_simplify(wmi_e, e_evaluated.expression)


        results = {}
        for k_q, v_q in sdds["queries"].items():
            qe_sdds = {k_s:sdd_manager.conjoin(v_q,v_s) for k_s,v_s in sdds["support"].items()}
            wmi_qe = psipy.S("0")
            for w in qe_sdds:
                tags = self.solver.get_tags(qe_sdds[w], semiring_tag, dde, **kwdargs)
                semiring.ww = poly2expr(sdds["ww"][w])
                semiring.tags = tags
                semiring.normalization = False
                qe_evaluated = dde.evaluate_sdd(qe_sdds[w], semiring, normalization=True, evaluation_last=False)
                wmi_qe = semiring.algebra.add_simplify(wmi_qe, qe_evaluated.expression)
            results[k_q] = (wmi_qe,wmi_e)

        #need to do this because did not use OrderedDict (idiot)
        results = [results[index] for index in range(0,len(results))]
        return results

    def compute_volume(self, timeout=None, **kwdargs):
        if timeout is None:
            timeout = self.timeout
        result = self.call_wmi(queries=[smt.TRUE()], timeout=timeout, **kwdargs)[0]
        if result is None or len(result) == 0:
            return None
        else:
            return result[0]

    def compute_probability(self, query, timeout=None, **kwdargs):
        result = self.compute_probabilities(queries=[query], timeout=timeout, **kwdargs)
        return result[0]

    def to_float(self, psypi_expression):
        string_representation = psipy.toString(psypi_expression)
        parts = string_representation.split("/", 1)
        if len(parts) > 1:
            return float(parts[0]) / float(parts[1])
        else:
            return float(parts[0])

    def compute_probabilities(self, queries, timeout=None, **kwdargs):
        # results = [psipy.div_simplify(qe,e) for qe,e in self.call_wmi()  ]
        results = [self.to_float(psipy.simplify(psipy.div(qe,e))) for qe,e in self.call_wmi(queries, timeout=None)]
        return results



class InferenceSolverWMI(InferenceSolver):
    def __init__(self, abe=None):
        InferenceSolver.__init__(self, abe)

class InferenceSolverWMIPint(InferenceSolverPINT):
    def __init__(self, abe=None, **kwdargs):
        InferenceSolverPINT.__init__(self, abe=abe, **kwdargs)


    def get_tags(self, sdd, semiring_tag, dde_tag, **kwdargs):
        e_int_tags, e_weight_tags = dde_tag.evaluate_sdd(sdd, semiring_tag, normalization=True, evaluation_last=False)
        e_weight_tags = self.weight_tags_val2key(e_weight_tags)
        return (e_int_tags, e_weight_tags)
