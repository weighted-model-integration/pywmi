import pytest
from pysmt.shortcuts import Ite, Real

from examples import inspect_manual
from pywmi import Domain, RejectionEngine

SAMPLE_COUNT = 1000000
REL_ERROR = 0.01


def test_manual():
    inspect_manual(lambda d, s, w: RejectionEngine(d, s, w, SAMPLE_COUNT), REL_ERROR)
