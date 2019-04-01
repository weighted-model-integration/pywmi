
from pysmt.shortcuts import *
from pywmi import Domain
from pywmi.errors import ParsingFileError
from pywmi.parser import MinizincParser#, SmtlibParser
from tempfile import TemporaryFile

def temporary_file(content):
    f = TemporaryFile(mode='w+')
    f.write(content)
    f.seek(0)
    return f



def test_parse_error():
    content = "this should raise a ParsingFileError"
    tmp = temporary_file(content)
    try:
        _ = MinizincParser.parseAll(tmp.name)
        assert False
    except ParsingFileError:
        assert True

def test_mzn1():
    content = """
var float:x;
var 0.0..2.0:y;

weight : if y < 1 then x+y else 2*y endif;

constraint (  y<1       -> (0<x /\ x<=2)  )
        /\ (  not (y<1) -> (1<x /\ x<3)  );
        
query (x>1.5);
query (x<=1.5);
query (true);
"""
    tmp = temporary_file(content)

    support, weights, domA, domX, queries = MinizincParser.parseAll(tmp.name)

    x, y = sorted(domX.keys(), key=lambda x : x.symbol_name())
    chi = And(Implies(LT(y, Real(1)), And(LT(Real(0), x), LE(x, Real(2)))),
              Implies(Not(LT(y, Real(1))), And(LT(Real(1), x), LT(x, Real(3)))))

    assert chi == support

    w = Ite(LT(y, Real(1)),
            Plus(x, y),
            Times(Real(2),y))

    assert w == weights
        
    phi1 = GE(x, Real(1.5))
    phi2 = LE(x, Real(1.5))
    phi3 = Bool(True)

    assert queries == [phi1, phi2, phi3]
