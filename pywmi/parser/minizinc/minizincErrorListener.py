import sys

from .antlr.minizincParser import minizincParser
from .antlr.minizincVisitor import minizincVisitor

from antlr4 import *
from antlr4.error.ErrorListener import *

from pywmi.errors import ParsingFileError
 
class MinizincErrorListener(ErrorListener):

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        raise ParsingFileError('Syntax error at line '+str(line)+', column '+str(column)+': '+msg)
