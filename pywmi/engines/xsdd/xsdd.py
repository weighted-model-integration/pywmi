import logging
import os
import re
import subprocess
import sys
from typing import Optional, List

from pysmt.fnode import FNode
from pysmt.shortcuts import Real, TRUE

from pywmi.domain import TemporaryDensityFile
from pywmi.engine import Engine

logger = logging.getLogger(__name__)


class XsddEngine(Engine):
    def __init__(self, domain, support, weight, mode=None, timeout=None):
        super().__init__(domain, support, weight)
        self.mode = mode
        self.timeout = timeout


    def call_wmi(self, queries=None, timeout=None):
        print(self.domain)
        print(self.support)
        print(self.weight)
        print("")

        return [1]


    def compute_volume(self, timeout=None):
        if timeout is None:
            timeout = self.timeout
        result = self.call_wmi(timeout=timeout)
        if result is None or len(result) == 0:
            return None
        else:
            return result[0]


    def copy(self, support, weight):
        return XsddEngine(self.domain, support, weight, self.mode, self.timeout)


    def __str__(self):
        result = "sadd:m{}".format(self.mode)
        if self.timeout is not None:
            result += ":t{}".format(self.timeout)
        return result
