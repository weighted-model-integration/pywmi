import logging
from collections import OrderedDict



# from pywmi.domain import TemporaryDensityFile
from pywmi.engine import Engine

from problog.cycles import break_cycles
from problog.formula import LogicFormula

from hal_problog.utils import load_string
from hal_problog.solver import SumOperator, InferenceSolver, InferenceSolverPINT

from .smt2pl import SMT2PL
from .evaluator import SemiringWMIPSI, SemiringWMIPSIPint, SemiringStaticAnalysisWMI, poly2expr


import psipy


logger = logging.getLogger(__name__)


class XsddEngine(Engine, SMT2PL):
    def __init__(self, domain, support, weight, mode=None, timeout=None, pint=False, collapse=False):
        Engine.__init__(self, domain, support, weight)
        SMT2PL.__init__(self, domain, support, weight)
        if pint:
            self.solver = InferenceSolverWMIPint(abe="psi")
        else:
            self.solver = InferenceSolverWMI(abe="psi")

        self.real_variables = domain.real_vars
        self.pint = pint
        self.collapse = collapse

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
            elif self.collapse:
                weight = self.calculate_weight_collapse(lf, operator, **kwdargs)
            else:
                weight = self.calculate_weight(lf, operator, **kwdargs)

            weights.append(weight)
        return weights

    @staticmethod
    def sort_sdds(sdds, worldweight, tags={}):
        sdds = sdds["qe"]
        n_queries = len(sdds)
        sdds_sorted = [{} for i in range(0,int(n_queries/2))]
        for s in sdds:
            if not "int_tags" in sdds_sorted[s.args[0].functor]:
                sdds_sorted[s.args[0].functor]["int_tags"] = {}
            if not "weight_tags" in sdds_sorted[s.args[0].functor]:
                sdds_sorted[s.args[0].functor]["weight_tags"] = {}

            if s.functor=="q":
                sdds_sorted[s.args[0].functor]["qe"]=sdds[s]
                sdds_sorted[s.args[0].functor]["int_tags"]["qe"] = tags.get(s,({},{}))[0]
                sdds_sorted[s.args[0].functor]["weight_tags"]["qe"] = tags.get(s,({},{}))[1]

            else:
                sdds_sorted[s.args[0].functor]["e"]=sdds[s]
                sdds_sorted[s.args[0].functor]["int_tags"]["e"] = tags.get(s,({},{}))[0]
                sdds_sorted[s.args[0].functor]["weight_tags"]["e"] = tags.get(s,({},{}))[1]


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

        import time
        t0 = time.time()
        for query in sdds:
            ww = poly2expr(query["ww"])
            e_evaluated = dde.evaluate_sdd(query["e"], semiring, normalization=False, evaluation_last=False)
            qe_evaluated = dde.evaluate_sdd(query["qe"], semiring, normalization=False, evaluation_last=False)
            if e_evaluated:
                w_e = semiring.integrate(ww, e_evaluated, self.real_variables)
                wmi_e = semiring.algebra.add_simplify(wmi_e, w_e)
                print(w_e)
            if qe_evaluated:
                w_qe = semiring.integrate(ww, qe_evaluated, self.real_variables)
                wmi_qe = semiring.algebra.add_simplify(wmi_qe, w_qe)
                print(w_qe)
        print("")
        print("time: {}".format(time.time()-t0))

        wmi = semiring.algebra.div_simplify(wmi_qe,wmi_e)
        return wmi


    def calculate_weight_collapse(self, lf, operator, **kwdargs):
        diagram = self.solver.compile_formula(lf, **kwdargs)
        semiring = SemiringWMIPSI(operator.get_neutral(), self.solver.abe)
        dde = diagram.get_evaluator(semiring=semiring, **kwdargs)
        sdds = dde.get_sdds()
        sdds = self.sort_sdds(sdds, self.worldweight)


        import time
        t0 = time.time()
        e_interval2weight = {}
        qe_interval2weight = {}
        for query in sdds:
            ww = poly2expr(query["ww"])
            e_evaluated = dde.evaluate_sdd(query["e"], semiring, normalization=False, evaluation_last=False)
            qe_evaluated = dde.evaluate_sdd(query["qe"], semiring, normalization=False, evaluation_last=False)

            if e_evaluated:
                e_evaluated_str = psipy.toString(e_evaluated.expression)

                if e_evaluated_str in e_interval2weight:
                    e_interval2weight[e_evaluated_str][1] = \
                        psipy.simplify(psipy.add(e_interval2weight[e_evaluated_str][1] , ww))
                else:
                    e_interval2weight[e_evaluated_str] = [e_evaluated, ww]

            if qe_evaluated:
                qe_evaluated_str = psipy.toString(qe_evaluated.expression)
                if qe_evaluated_str  in qe_interval2weight:
                    qe_interval2weight[qe_evaluated_str][1] = \
                        psipy.simplify(psipy.add(qe_interval2weight[qe_evaluated_str][1] , ww))
                else:
                    qe_interval2weight[qe_evaluated_str] = [qe_evaluated, ww]


        wmi_e = semiring.zero().expression
        wmi_qe = semiring.zero().expression


        t1 = time.time()
        for i in e_interval2weight:
            print("")
            print(e_interval2weight[i])
            w_e = semiring.integrate(e_interval2weight[i][1], e_interval2weight[i][0], self.real_variables)
            wmi_e = semiring.algebra.add_simplify(wmi_e, w_e)
            print(w_e)
        for i in qe_interval2weight:
            print("")
            print(qe_interval2weight[i])

            w_qe = semiring.integrate(qe_interval2weight[i][1], qe_interval2weight[i][0], self.real_variables)
            wmi_qe = semiring.algebra.add_simplify(wmi_qe, w_qe)
            print(w_qe)
        print("")
        print("time: {}".format(time.time()-t1))
        print("time: {}".format(time.time()-t0))

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
        tags = tags["qe"]

        sdds = self.sort_sdds(sdds, self.worldweight, tags=tags)


        wmi_e = semiring.zero().expression
        wmi_qe = semiring.zero().expression

        for query in sdds:
            ww = poly2expr(query["ww"])
            int_tags_e = query["int_tags"]["e"]
            weight_tags_e = query["weight_tags"]["e"]
            int_tags_qe = query["int_tags"]["qe"]
            weight_tags_qe = query["weight_tags"]["qe"]


            semiring.ww = ww

            semiring.tags = (int_tags_e, weight_tags_e)
            semiring.normalization = True
            e_evaluated = dde.evaluate_sdd(query["e"], semiring, normalization=False, evaluation_last=False)
            semiring.ww = ww
            semiring.tags = (int_tags_qe, weight_tags_qe)
            semiring.normalization = False
            qe_evaluated = dde.evaluate_sdd(query["qe"], semiring, normalization=False, evaluation_last=False)

            if e_evaluated:
                w_e = e_evaluated.expression
                wmi_e = semiring.algebra.add_simplify(wmi_e, w_e)

            if qe_evaluated:
                w_qe = qe_evaluated.expression
                wmi_qe = semiring.algebra.add_simplify(wmi_qe, w_qe)

            # print(wmi_qe)
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

class InferenceSolverWMIPint(InferenceSolverPINT):
    def __init__(self, abe=None, **kwdargs):
        InferenceSolverPINT.__init__(self, abe=abe, **kwdargs)


    def get_tags(self, sdds, semiring_tag, dde_tag, **kwdargs):
        tags = {}
        e_int_tags, e_weight_tags = dde_tag.evaluate_sdd(sdds["e"], semiring_tag, normalization=True, evaluation_last=False)
        e_weight_tags = self.weight_tags_val2key(e_weight_tags)
        tags["e"] = (e_int_tags, e_weight_tags)

        tags["qe"] = OrderedDict()

        for q, qe_sdd in sdds["qe"].items():
            qe_ev_result = dde_tag.evaluate_sdd(qe_sdd, semiring_tag, evaluation_last=False)
            if isinstance(qe_ev_result,tuple):
                # qe_int_tags, qe_weight_tags = dde_tag.evaluate_sdd(qe_sdd, semiring_tag, evaluation_last=False)
                qe_int_tags, qe_weight_tags = qe_ev_result

            else:
                qe_int_tags, qe_weight_tags = ({},{})
            qe_weight_tags = self.weight_tags_val2key(qe_weight_tags)

            tags["qe"][q] = (qe_int_tags, qe_weight_tags)

        return tags
