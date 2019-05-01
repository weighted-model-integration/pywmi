from antlr4 import *
from pysmt.shortcuts import *
import io

from .antlr.minizincLexer import minizincLexer
from .antlr.minizincParser import minizincParser
from .visitor import Visitor
from .minizincErrorListener import MinizincErrorListener

class MinizincParser():

    @staticmethod
    def parse(path, domA=None, domX=None, weight=None):
        if domA is None:
            domA = []
        if domX is None:
            domX = {}
        
        # init lexer and parser
        mzn_file = FileStream(path)
        lexer = minizincLexer(mzn_file)
        stream = CommonTokenStream(lexer)
        parser = minizincParser(stream)
        
        # add custom error listener
        parser.removeErrorListeners()
        errorListener = MinizincErrorListener()
        parser.addErrorListener(errorListener)
        
        # compute parsing
        tree = parser.minizinc()
        
        # visit the tree
        visitor = Visitor(path, domA=domA, domX=domX, weight=weight)
        return visitor.visit(tree)
