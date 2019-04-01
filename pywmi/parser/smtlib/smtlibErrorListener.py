import sys

from .antlr.smtlibParser import smtlibParser
from .antlr.smtlibVisitor import smtlibVisitor

from pywmi.errors import ParsingFileError
 
class SmtlibErrorListener():

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        raise ParsingFileError('Syntax error at line '+str(line)+', column '+str(column)+': '+msg)
