
from collections import OrderedDict
import functools

from pysmt.environment import Environment
from pysmt.operators import (AND, OR, NOT, IMPLIES, IFF, ITE,
    SYMBOL, REAL_CONSTANT, BOOL_CONSTANT, INT_CONSTANT,
    PLUS, MINUS, TIMES, POW, LE, LT, EQUALS)
from pysmt.typing import REAL, BOOL
from pysmt.fnode import FNode

from pywmi.smt_math import LinearInequality
from pywmi.smt_walk import SmtWalker


class InverseDictDelegate(dict):
    def __init__(self, *a, inverse, on_change=lambda: None, **kw):
        super().__init__(*a, **kw)
        self.inverse = inverse
        self.on_change = on_change

    def __setitem__(self, key, item):
        assert (key in self) or (item not in self.inverse), "Don't override existing key"
        super().__setitem__(key, item)
        self.inverse[item] = key
        self.on_change()

    def __delitem__(self, key):
        super().__delitem__(key)
        item = self[key]
        del self.inverse[item]
        self.on_change()

    def clear(self):
        for key, item in self.items():
            assert item in self.inverse
        for key, item in self.items():
            super().__delitem__(key)
            del self.inverse[item]
        self.on_change()


class LiteralInfo:
    def __init__(self, abstractions, booleans):
        self.literals = OrderedDict()
        # TODO: right now, some part of the code does lookups literal -> boolean/abstraction
        # The way to do that easily is an isinstance check, since booleans are strings and abstractions
        # are FNodes. However, this could be cleaner.
        assert len(set(booleans.values()) & set(abstractions.values())) == 0, "Overlapping literals"
        for var, lit in booleans.items():
            self.literals[lit] = var
        for formula, lit in abstractions.items():
            self.literals[lit] = formula

        self._numbered_cache = None
        self._inv_numbered_cache = None
        self._numbered_cache_ok = False

        self.abstractions = InverseDictDelegate(abstractions, inverse=self.literals, on_change=self._on_change)
        self.booleans = InverseDictDelegate(booleans, inverse=self.literals, on_change=self._on_change)

    @property
    def numbered(self):
        self._recalc_numbered()
        return self._numbered_cache

    @property
    def inv_numbered(self):
        self._recalc_numbered()
        return self._inv_numbered_cache

    def _on_change(self):
        self._numbered_cache_ok = False

    def _recalc_numbered(self):
        if not self._numbered_cache_ok:
            self._numbered_cache = {lit: num+1 for num, lit in enumerate(self.literals)}
            self._inv_numbered_cache = {num+1: lit for num, lit in enumerate(self.literals)}

    def __getitem__(self, key):
        return self.literals[key]

    def __iter__(self):
        return iter(self.literals.keys())


def to_canonical(test_node):
    return LinearInequality.from_smt(test_node).normalize().to_smt()


LOGIC_TYPES = {AND, OR, NOT, IMPLIES, IFF, ITE}
TEST_TYPES  = {LE, LT, EQUALS}
REAL_TYPES  = {TIMES, PLUS, MINUS, POW, REAL_CONSTANT, INT_CONSTANT, SYMBOL}


def is_all_real(formula):
    if formula.node_type() == SYMBOL:
        return formula.symbol_type() == REAL
    elif formula.node_type() == REAL_CONSTANT or formula.node_type() == INT_CONSTANT:
        return True
    elif formula.node_type() in REAL_TYPES:
        return all(is_all_real(arg) for arg in formula.args())
    else:
        return False


def extract_and_replace_literals(formula: FNode, cache_size=512) -> (Environment, FNode, LiteralInfo):
    abstractions = {}
    booleans = {}

    env = Environment()
    fm = env.formula_manager

    build_logic = {
        AND: fm.And, OR: fm.Or, NOT: fm.Not,
        IMPLIES: fm.Implies, IFF: fm.Iff,
        ITE: fm.Ite
    }

    @functools.lru_cache(maxsize=cache_size)
    def recurse(formula):
        if formula.node_type() == BOOL_CONSTANT:
            return formula
        if formula.node_type() == SYMBOL:
            assert formula.symbol_type() == BOOL
            if formula.symbol_name() not in booleans:
                booleans[formula.symbol_name()] = f"b{len(booleans)}"
            return fm.Symbol(booleans[formula.symbol_name()])
        elif formula.node_type() in LOGIC_TYPES:
            return build_logic[formula.node_type()](
                *(recurse(arg) for arg in formula.args()))
        elif formula.node_type() in TEST_TYPES:
            assert all(is_all_real(arg) for arg in formula.args()), "Wrong test expression"
            canonical_formula = to_canonical(formula)
            if canonical_formula not in abstractions:
                abstractions[canonical_formula] = f"a{len(abstractions)}"
            return fm.Symbol(abstractions[canonical_formula])
        else:
            raise RuntimeError(f"Cannot extract literals from {formula}")

    repl_formula = recurse(formula)
    # TODO: having to return env here is a bit ugly? Might be redundant, but I'd rather be safe
    return env, repl_formula, LiteralInfo(abstractions, booleans)
