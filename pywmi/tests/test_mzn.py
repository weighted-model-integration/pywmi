import pytest
from pysmt.shortcuts import *
from pysmt.exceptions import NoSolverAvailableError
from pywmi import Domain
from pywmi.errors import ParsingFileError
from pywmi.parser import MinizincParser#, SmtlibParser
from tempfile import NamedTemporaryFile

try:
    is_sat(Bool(True))
    solver_available = True
except NoSolverAvailableError:
    solver_available = False
    
def temporary_file(content):
    f = NamedTemporaryFile(mode='w+')
    f.write(content)
    f.seek(0)
    return f

def test_syntax_error():
    content = "this should raise a ParsingFileError!"
    tmp = temporary_file(content)
    try:
        _ = MinizincParser.parse(tmp.name)
        assert False
    except ParsingFileError:
        assert True

def test_double_weight_decl_error():
    content = """
var float:x;
var 0.0..2.0:y;

weight : if y < 1 then x+y else 2*y endif;
weight : if y < 1 then x+y else 2*y endif;

constraint (  y<1       -> (0<x /\ x<=2)  )
        /\ (  not (y<1) -> (1<x /\ x<3)  );
        
query (x>1.5);
query (x<=1.5);
query (true);
"""
    tmp = temporary_file(content)
    try:
        _ = MinizincParser.parse(tmp.name)
        assert False
    except ParsingFileError:
        assert True

@pytest.mark.skipif(not solver_available, reason="No Solver is available")
def test_correct_parsing1():
    content = """
var -1.5..1.0:x;
var 0.0..2.0:y;

constraint x < y ;       
"""
    tmp = temporary_file(content)

    support, weights, domA, domX, queries, _ = MinizincParser.parse(tmp.name)

    x, y = sorted(domX.keys(), key=lambda x : x.symbol_name())
    chi = LT(x, y)

    # chi == support
    assert not is_sat(Or(And(chi, Not(support)), And(Not(chi), support)))

    w = Real(1)

    assert w == weights
        
    assert domX[x] == [Real(-1.5), Real(1.0)]
    assert domX[y] == [Real(0.0), Real(2.0)]


@pytest.mark.skipif(not solver_available, reason="No Solver is available")
def test_correct_parsing2():
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

    support, weights, domA, domX, queries, _ = MinizincParser.parse(tmp.name)

    x, y = sorted(domX.keys(), key=lambda x : x.symbol_name())
    chi = And(Implies(LT(y, Real(1)), And(LT(Real(0), x), LE(x, Real(2)))),
              Implies(Not(LT(y, Real(1))), And(LT(Real(1), x), LT(x, Real(3)))))

    # chi == support
    assert not is_sat(Or(And(chi, Not(support)), And(Not(chi), support)))

    w = Ite(LT(y, Real(1)),
            Plus(x, y),
            Times(y, Real(2)))

    assert w == weights

    assert domX[y] == [Real(0.0), Real(2.0)]
        
    phi1 = GT(x, Real(1.5))
    phi2 = LE(x, Real(1.5))
    phi3 = Bool(True)

    assert queries == [phi1, phi2, phi3]
    
    
@pytest.mark.skipif(not solver_available, reason="No Solver is available")
def test_correct_parsing3():
    content = """
var 0.0..10.0:x;
var bool:a;

weight : if a then 2*x else x endif;

constraint (a -> (x>5));
        
query (x>2);
query (x<=8);
"""
    
    tmp = temporary_file(content)

    support, weights, domA, domX, queries, _ = MinizincParser.parse(tmp.name)

    x = list(domX.keys())[0]
    a = list(domA)[0]
    
    chi = Implies(a, LT(Real(5), x))

    # chi == support
    assert not is_sat(Or(And(chi, Not(support)), And(Not(chi), support)))

    w = Ite(a,
            Times(x, Real(2)),
            x)

    assert w == weights

    assert domX[x] == [Real(0.0), Real(10.0)]
        
    phi1 = GT(x, Real(2))
    phi2 = LE(x, Real(8))

    assert queries == [phi1, phi2]


@pytest.mark.skipif(not solver_available, reason="No Solver is available")
def test_correct_type_parsing():
    content = """
var -5..5.0:x;      % here the first element is int
var -5.0..5:y;      % here the second element is int
"""

    tmp = temporary_file(content)

    support, weights, domA, domX, queries, _ = MinizincParser.parse(tmp.name)
    
    x, y = sorted(domX.keys(), key=lambda x : x.symbol_name())
    
    chi = Bool(True)
    
    # chi == support
    assert not is_sat(Or(And(chi, Not(support)), And(Not(chi), support)))
    
    w = Real(1)
    
    assert w == weights
    
    assert domX[x] == [Real(-5.0), Real(5.0)]
    assert domX[y] == [Real(-5.0), Real(5.0)]
    
    assert queries == []
    
    
@pytest.mark.skipif(not solver_available, reason="No Solver is available")
def test_parameter_and_variable():
    content = """
float:min = 0.0;
par float:max = 10.0;
var min..max:x;
"""
    
    tmp = temporary_file(content)

    support, weights, domA, domX, queries, _ = MinizincParser.parse(tmp.name)
    
    x = list(domX.keys())[0]
    
    chi = Bool(True)
    
    # chi == support
    assert not is_sat(Or(And(chi, Not(support)), And(Not(chi), support)))
    
    w = Real(1)
    
    assert w == weights
    
    assert domX[x] == [Real(0.0), Real(10.0)]
    
    assert queries == []
    

def test_error_parameter_with_range():
    content = """
float:min = 0.0;
par float:max = 10.0;
par min..max:x;         % here x is defined as a parameter (and not a variable)
"""

    tmp = temporary_file(content)
    
    try:
        _ = MinizincParser.parse(tmp.name)
        assert False
    except ParsingFileError:
        assert True
