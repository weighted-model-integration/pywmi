import sys

from .antlr.smtlibParser import smtlibParser
from .antlr.smtlibVisitor import smtlibVisitor

from antlr4 import *
from antlr4.error.ErrorListener import *

from pywmi.errors import ParsingFileError
 
class SmtlibErrorListener(ErrorListener):

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        raise ParsingFileError('Syntax error at line '+str(line)+', column '+str(column)+': '+msg)
