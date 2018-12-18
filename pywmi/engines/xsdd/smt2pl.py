from pysmt import shortcuts


class SMT2PL(object):
    def __init__(self, domain, support, weight):
        self.problog_program = WMIPL(domain, support, weight, domain.bool_vars)
        self.weight_function = self.problog_program.weight_function
        self.worldweight = self.problog_program.weight_literal2weight_function


class WMIPL(object):
    def __init__(self, domain, support, weight, booleans):


        self.literal_count = -1
        self.condition_count = -1
        self.weight_count = -1
        self.weight_condition_count = -1

        self.booleans = booleans

        self.weight_function2weight_literal = {}
        self.weight_literal2weight_function = {}
        self.weight_conditions = {}
        self.boolean_variables = []
        self.weight_function = self.logicalize_weight(weight)

        self.string_program = ""
        self.add_query("q(_)")
        self.add_query("e(_)")

        self.add_weight(self.weight_function)
        self.string_program += "\nweight(X):-ww(X).\n"
        self.add_free_bools()

        self.add_smt_evidence(domain, support)


    def add_smt_evidence(self, domain, support):
        self.string_program += "\n"
        evidence = self._smt2pl(domain.get_bounds() & support)
        rule = self.make_rule(head="e(X)", body=(evidence,"weight(X)"))
        self.add_rule(rule)

    def add_smt_query(self, query):
        self.string_program += "\n"
        query = self._smt2pl(query)
        rule = self.make_rule(head="q(X)", body=(query,"e(X)"))
        # not sure which one is better, conjoin here or only later the sdds?
        # rule = self.make_rule(head="q(X)", body=(query,)
        self.add_rule(rule)

    def add_free_bools(self):
        free_booleans = [f for f in self.booleans if f not in self.boolean_variables]
        self.string_program += "\n"
        self.string_program += "a::"
        self.string_program += ".\na::".join(map(str.lower,free_booleans))
        self.string_program += ".\n"



    def _smt2pl(self, expression):
        if expression.is_and():
            children = [self._smt2pl(arg) for arg in expression.args()]
            children = [c for c in children if c.startswith("c(") or c.startswith("l(")]
            literal = self.new_literal()
            rule = self.make_rule(head=literal,body=children)
            self.add_rule(rule)
            return literal
        elif expression.is_or():
            children = [self._smt2pl(arg) for arg in expression.args()]
            literal = self.new_literal()
            for c in children:
                rule = self.make_rule(head=literal, body=(c,))
                self.add_rule(rule)
            return literal
        elif expression.is_implies():
            child1 = self._smt2pl(expression.args()[0])
            child2 = self._smt2pl(expression.args()[1])
            literal = self.new_literal()
            rule1 = self.make_rule(head=literal, body=("\+{}".format(child1),))
            rule2 = self.make_rule(head=literal, body=(child1,child2))
            self.add_rule(rule1)
            self.add_rule(rule2)
            return literal
        elif expression.is_iff():
            head, body = self.find_hb(expression)
            head = head.lower()
            self.boolean_variables.append(head)
            body = self._smt2pl(body)
            rule = self.make_rule(head=head, body=(body,))
            self.add_rule(rule)
            return head
        elif expression.is_true():
            literal = self.new_literal()
            rule = self.make_rule(head=literal)
            self.add_rule(rule)
            return literal
        if expression.is_not():
            literal = self._smt2pl(expression.args()[0])
            return "\+{}".format(literal)
        elif expression.is_le() or expression.is_lt() or expression.is_equals():
            literal = self.new_condition()
            fact = self.make_condition_fact(head=literal, label=expression)
            self.add_rule(fact)
            return literal
        elif expression.is_symbol():
            if shortcuts.serialize(expression).startswith("A_"):
                literal = self.new_literal()
                rule = self.make_rule(head=literal, body=(shortcuts.serialize(expression).lower(),))
                self.add_rule(rule)
                return literal
            return str(expression)
        # elif expression.is_constant():
        #     literal = self.new_weight()
        #     self.string_program += "{literal}.\n".format(literal=literal)
        #     poly_weight = expression
        #     self.poly_weights[self.weight_count] = poly_weight
        #     return self.weight_count

    def find_hb(self, expression):
        args = expression.args()
        if args[0].is_symbol():
            head, body = args
        else:
            body, head = args
        return str(head).lower(), body

    def new_literal(self):
        self.literal_count += 1
        literal = "l({literal_count})".format(literal_count=self.literal_count)
        return literal
    def new_condition(self):
        self.condition_count += 1
        literal = "c({condition_count})".format(condition_count=self.condition_count)
        return literal
    def new_weight(self, expression):
        if expression in self.weight_function2weight_literal:
            return "ww({weight_count})".format(weight_count=self.weight_function2weight_literal[expression])
        else:
            self.weight_count += 1
            literal = "ww({weight_count})".format(weight_count=self.weight_count)
            self.weight_function2weight_literal[expression] = self.weight_count
            self.weight_literal2weight_function[self.weight_count] = shortcuts.serialize(expression)
            return literal
    def new_weight_condition(self, condition):
        if condition in self.weight_conditions:
            return self.weight_conditions[condition]
        else:
            self.weight_condition_count += 1
            literal = "wc({weight_condition_count})".format(weight_condition_count=self.weight_condition_count)
            self.weight_conditions[condition] = literal
        return literal

    def add_rule(self, rule):
        self.string_program += rule
    def add_query(self, query):
        self.string_program += "query({}).\n".format(query)
    def add_weight(self, expression, parent=[]):
        if expression.is_ite():
            condition, pos, neg = expression.args()
            con = self.algebra2pl(condition)
            weight_literal = self.new_weight_condition(con)
            rule_con = self.make_weight_rules(condition, weight_literal)
            self.add_rule(rule_con)

            p_pos = parent + [weight_literal]
            self.add_weight(pos, parent=p_pos)
            p_neg  = parent + ["\+{}".format(weight_literal)]
            self.add_weight(neg, parent=p_neg)
        else:
            weight_literal = self.new_weight(expression)
            rule_con = self.make_world_weight_rule(weight_literal, parent=parent)
            self.add_rule(rule_con)



    def algebra2pl(self, expression):
        expression=str(expression).strip().replace(" ","")
        if expression.startswith("("):
            expression = expression[1:-1]
        expression = "'{}'".format(expression)
        return expression

    def make_rule(self, head=None, body=None):
        if body:
            body = [b.lower() if b.startswith("A") else b  for b in body]
            body = ",".join(body)
            return "{head}:-{body}.\n".format(head=head, body=body)
        else:
            return  "{head}.\n".format(head=head)
    def make_condition_fact(self, head, label):
        variables = list(label.get_free_variables())
        if str(label).startswith("("):
            label = "'"+str(label)[1:-1].replace(" ","")+"'"
        fact = "con({label},{variables})::{head}.\n".format(label=label, variables=variables, head=head)
        return fact
    def make_world_weight_rule(self, weight_literal, parent=None):
        if parent :
            body = ",".join(parent)
            rule_con = "{head}:-{body}.\n".format(head=weight_literal,body=body)
        elif not parent:
            rule_con = "{head}.\n".format(head=weight_literal)
        return rule_con
    def make_weight_rules(self, condition, weight_literal, parent=None):
        con = self.algebra2pl(condition)
        if parent and not condition.is_literal():
            variables = list(condition.get_free_variables())
            rule_con = "con({condition},{variables})::{head}:-{body}.\n".format(condition=con,variables=variables,head=weight_literal,body=parent)
        elif parent and condition.is_literal():
            rule_con = "{head}:-{condition},{body}.\n".format(condition=con[1:-1].lower(),head=weight_literal,body=parent)
        elif not parent and not condition.is_literal():
            variables = list(condition.get_free_variables())
            rule_con = "con({condition})::{head}.\n".format(condition=con,variables=variables,head=weight_literal)
        elif not parent and condition.is_literal():
            rule_con = "{head}:-{condition}.\n".format(condition=con[1:-1].lower(),head=weight_literal)
        return rule_con

    def apply_operation(self, operation, args):
        if len(args)==2:
            return self.binary_apply_operation(operation, args[0], args[1])
        else:
            bapply = self.binary_apply_operation(operation, args[0], args[1])
            return self.apply_operation(operation, [bapply] + args[2:])
    def binary_apply_operation(self, operation, arg1, arg2):
        if not arg1.is_ite() and not arg2.is_ite():
            return shortcuts.simplify(operation(arg1,arg2))
        elif arg1.is_ite() and not arg2.is_ite():
            a1  = self.binary_apply_operation(operation, arg1.args()[1], arg2)
            a2  = self.binary_apply_operation(operation, arg1.args()[2], arg2)
            return shortcuts.Ite(arg1.args()[0], a1, a2)
        elif not arg1.is_ite() and arg2.is_ite():
            a1  = self.binary_apply_operation(operation, arg1, arg2.args()[1])
            a2  = self.binary_apply_operation(operation, arg1, arg2.args()[2])
            return shortcuts.Ite(arg2.args()[0], a1, a2)
        elif arg1.is_ite() and arg2.is_ite():
            a1  = self.binary_apply_operation(operation, arg1.args()[1], arg2)
            a2  = self.binary_apply_operation(operation, arg1.args()[2], arg2)
            return shortcuts.Ite(arg1.args()[0], a1, a2)

    def logicalize_weight(self, expression):
        if expression.is_ite():
            args = expression.args()
            condition = args[0]
            child1 = expression.args()[1]
            child2 = expression.args()[2]
            result =  shortcuts.Ite(condition,self.logicalize_weight(child1), self.logicalize_weight(child2))
            return result
        elif expression.is_times():
            children = expression.args()
            children = [self.logicalize_weight(c) for c in children]
            result = self.apply_operation(shortcuts.Times, children)
            return  result
        elif expression.is_plus():
            children = expression.args()
            children = [self.logicalize_weight(c) for c in children]
            result = self.apply_operation(shortcuts.Plus, children)
            return  result
        else:
            return expression
