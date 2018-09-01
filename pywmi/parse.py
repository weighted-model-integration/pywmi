import fractions
import pysmt.shortcuts as smt
from pysmt.operators import POW, IMPLIES


class Node(object):
    def __init__(self, name=None):
        self.name = name
        self.children = []

    def has_name(self):
        return self.name is not None

    def __repr__(self):
        return "Node({}, {})".format(self.name, self.children)


def string_to_ast(string, operators=None):
    return tokenized_string_to_ast(tokenize(string), operators)


def tokenize(chars):
    """Convert a string of characters into a list of tokens."""
    return chars.replace('(', ' ( ').replace(')', ' ) ').split()


def tokenized_string_to_ast(tokenized_string, operators=None):
    stack = []
    root = None
    operators = set(operators) if operators is not None else None
    for token in tokenized_string:
        current = stack[-1] if len(stack) > 0 else None
        if token == "(":
            node = Node()
            stack.append(node)
            if current is not None:
                current.children.append(node)
            else:
                root = node
        elif token == ")":
            stack.pop()
        else:
            if current.has_name():
                current.children.append(Node(token))
            else:
                if operators is not None and token not in operators:
                    raise RuntimeError("Disallowed token '{}'".format(token))
                current.name = token
    return root


def nested_to_smt(string):
    return SmtParser().parse_smt(string)


def combined_nested_to_wmi(string):
    return SmtParser().parse_wmi_combined(string)


class SmtParser(object):
    operators = ["ite", "^", "~", "&", "|", "*", "+", "-", "<=", "<", ">", ">=", "->", "=", "const", "var"]

    def __init__(self):
        self.vars = dict()

    def parse_smt(self, nested_string):
        return self.ast_to_smt(string_to_ast(nested_string, self.operators))

    def parse_wmi_combined(self, nested_string):
        ast = string_to_ast(nested_string, self.operators)
        weights_node = Node(ast.name)
        weights_node.children = ast.children[1:]
        return self.ast_to_smt(ast.children[0]), self.ast_to_smt(weights_node)

    def ast_to_smt(self, node):
        """
        :type node: Node
        """

        def convert_children(number=None):
            if number is not None and len(node.children) != number:
                raise Exception("The number of children ({}) differed from {}".format(len(node.children), number))
            return [self.ast_to_smt(child) for child in node.children]

        if node.name == "ite":
            return smt.Ite(*convert_children(3))
        elif node.name == "~":
            return smt.Not(*convert_children(1))
        elif node.name == "^":
            return smt.Pow(*convert_children(2))
        elif node.name == "&":
            return smt.And(*convert_children())
        elif node.name == "|":
            return smt.Or(*convert_children())
        elif node.name == "*":
            return smt.Times(*convert_children())
        elif node.name == "+":
            return smt.Plus(*convert_children())
        elif node.name == "-":
            return smt.Minus(*convert_children(2))
        elif node.name == "<=":
            return smt.LE(*convert_children(2))
        elif node.name == ">=":
            return smt.GE(*convert_children(2))
        elif node.name == "<":
            return smt.LT(*convert_children(2))
        elif node.name == ">":
            return smt.GT(*convert_children(2))
        elif node.name == "=":
            return smt.Equals(*convert_children(2))
        elif node.name == "const":
            c_type, c_value = [child.name for child in node.children]
            if c_type == "bool":
                return smt.Bool(bool(c_value))
            elif c_type == "real":
                return smt.Real(float(c_value))
            else:
                raise Exception("Unknown constant type {}".format(c_type))
        elif node.name == "var":
            v_type, v_name = [child.name for child in node.children]
            if v_type == "bool":
                v_smt_type = smt.BOOL
            elif v_type == "real":
                v_smt_type = smt.REAL
            else:
                raise Exception("Unknown variable type {}".format(v_type))
            return smt.Symbol(v_name, v_smt_type)
        else:
            raise RuntimeError("Unrecognized node type '{}'".format(node.name))


def smt_to_nested(expression):
    """
    Converts an smt expression to a nested formula
    :param expression: An SMT expression (FNode)
    :return: A string representation (lisp-style)
        Functional operators can be: &, |, *, +, <=, <, ^
        Variables are represented as (var type name)
        Constants are represented as (const type name)
        Types can be: real, int, bool
    """
    def convert_children(op):
        return "({} {})".format(op, " ".join(smt_to_nested(arg) for arg in expression.args()))

    def format_type(smt_type):
        if smt_type == smt.REAL:
            return "real"
        if smt_type == smt.INT:
            return "int"
        if smt_type == smt.BOOL:
            return "bool"
        raise RuntimeError("No type corresponding to {}".format(smt_type))

    if expression.is_and():
        return convert_children("&")
    if expression.is_or():
        return convert_children("|")
    if expression.node_type() == IMPLIES:
        return smt_to_nested(smt.Or(smt.Not(expression.args()[0]), expression.args()[1]))
    if expression.is_iff():
        return smt_to_nested(smt.And(
            smt.Implies(expression.args()[0], expression.args()[1]),
            smt.Implies(expression.args()[1], expression.args()[0])
        ))
    if expression.is_not():
        return convert_children("~")
    if expression.is_times():
        return convert_children("*")
    if expression.is_plus():
        return convert_children("+")
    if expression.is_minus():
        return convert_children("-")
    if expression.is_ite():
        return convert_children("ite")
    if expression.node_type() == POW:
        exponent = expression.args()[1]
        if exponent.is_constant() and exponent.constant_value() == 1:
            return smt_to_nested(expression.args()[0])
        else:
            return convert_children("^")
    if expression.is_le():
        return convert_children("<=")
    if expression.is_lt():
        return convert_children("<")
    if expression.is_equals():
        return convert_children("=")
    if expression.is_symbol():
        return "(var {} {})".format(format_type(expression.symbol_type()), expression.symbol_name())
    if expression.is_constant():
        value = expression.constant_value()
        if isinstance(value, fractions.Fraction):
            value = float(value)
        return "(const {} {})".format(format_type(expression.constant_type()), value)

    raise RuntimeError("Cannot convert {} (of type {})".format(expression, expression.node_type()))
