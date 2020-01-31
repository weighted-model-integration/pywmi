import sympy
import pysmt.shortcuts as smt

def pysmt2sympy(expression):
    import sympy
    serialize_formula = smt.serialize(expression)
    try:
        sympy_formula = sympy.sympify(serialize_formula)
    except sympy.SympifyError:
        raise ValueError
    return sympy_formula
def sympy2pysmt(expression):
    if expression.is_Add:
        return smt.Plus(map(sympy2pysmt, expression.args))
    elif expression.is_Mul:
        return smt.Times(map(sympy2pysmt, expression.args))
    elif expression.is_Pow:
        base, exp = expression.args
        return smt.Pow(sympy2pysmt(base), sympy2pysmt(exp))
    elif expression.is_Symbol:
        return smt.Symbol(str(expression), smt.REAL)
    elif expression.is_Number:
        return smt.Real(float(expression))
    else:
        raise ValueError
