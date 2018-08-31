import logging
import os
import re
import subprocess
import sys
from typing import Optional, List

from pysmt.fnode import FNode

from pywmi.engine import Engine

logger = logging.getLogger(__name__)


class XaddEngine(Engine):
    pattern = re.compile(r"\n(\d+\.\d+) (\d+\.\d+)\n")

    def __init__(self, domain, support, weight, mode, timeout=None):
        super().__init__(domain, support, weight)
        self.mode = mode
        self.timeout = timeout

    def call_wmi(self, queries=None, timeout=None):
        # type: (Optional[List[FNode]], Optional[int]) -> List[Optional[float]]
        class_path = "/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/charsets.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/deploy.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/ext/cldrdata.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/ext/dnsns.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/ext/jaccess.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/ext/jfxrt.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/ext/localedata.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/ext/nashorn.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/ext/sunec.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/ext/sunjce_provider.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/ext/sunpkcs11.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/ext/zipfs.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/javaws.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/jce.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/jfr.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/jfxswt.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/jsse.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/management-agent.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/plugin.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/resources.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/jre/lib/rt.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/lib/ant-javafx.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/lib/dt.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/lib/javafx-mx.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/lib/jconsole.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/lib/packager.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/lib/sa-jdi.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_151.jdk/Contents/Home/lib/tools.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/out/production/XADD:/Users/samuelkolb/Documents/PhD/WMI/XADD/out/production/Util:/Users/samuelkolb/Documents/PhD/WMI/XADD/out/production/xadd-inference:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/trueskill/lombok.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/trueskill/lombok.zip:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/trueskill/testng.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/trueskill/testng.zip:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/trueskill/ejml-0.11.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/trueskill/ejml-0.11-src.zip:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/batik-awt-util-1.7.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/batik-svggen-1.7.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/batik-util-1.7.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/grappa1_4.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/java_cup.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/jlex.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/jmatio.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/junit-4.7.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/liblinear-1.8.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/PlotPackage.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/surfaceplot.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/xml-apis-1.3.04.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/colt-1.2.0.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/commons-beanutils-1.7.0.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/commons-digester-1.8.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/architecture-rules-2.1.1.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/commons-lang3-3.2.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/commons-logging-1.1.1.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/commons-math3-3.3.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/concurrent-1.3.4.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/csparsej-1.1.1.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/GLPKSolverPack.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/hamcrest-core-1.3.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/javassist-3.0.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/jdepend-2.9.1.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/joptimizer-3.5.0.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/log4j-1.2.14.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/SCPSolver.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/utils-1.07.00.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/LPSOLVESolverPack.jar:/Users/samuelkolb/Documents/PhD/xadd-inference/lib/gurobi.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/architecture-rules-2.1.1.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/colt-1.2.0.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/commons-beanutils-1.7.0.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/commons-digester-1.8.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/commons-lang3-3.2.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/commons-logging-1.1.1.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/commons-math3-3.3.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/concurrent-1.3.4.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/csparsej-1.1.1.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/GLPKSolverPack.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/hamcrest-core-1.3.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/javassist-3.0.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/jdepend-2.9.1.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/joptimizer-3.5.0.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/log4j-1.2.14.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/SCPSolver.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/utils-1.07.00.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/kotlin-reflect.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/kotlin-stdlib.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/LPSOLVESolverPack.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/gurobi.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/gson-2.6.2.jar:/Users/samuelkolb/Documents/PhD/WMI/XADD/lib/json.jar"

        filename = self.wmi_to_file(queries)

        try:
            args = ["java", "-classpath", class_path, "diagram.QueryEngineKt", filename, self.mode]
            logger.info("> {}".format(" ".join(args)))
            output = subprocess.check_output(args, timeout=timeout).decode(sys.stdout.encoding)
            return [(float(match[0]) if queries is not None else float(match[1]))
                    for match in XaddEngine.pattern.findall(output)]
            #     xadd_volume = float(output.split("\\n")[-3].split(" ")[0])
        except subprocess.CalledProcessError as e:
            logger.warning(e.output)
            return [None for _ in range(1 if queries is None else len(queries))]
        except subprocess.TimeoutExpired:
            return [None for _ in range(1 if queries is None else len(queries))]
        except ValueError:
            output = str(subprocess.check_output(["cat", filename]))
            logger.warning("File content:\n{}".format(output))
            raise
        finally:
            os.remove(filename)

    def compute_volume(self, timeout=None):
        if timeout is None:
            timeout = self.timeout
        return self.call_wmi(timeout=timeout)[0]

    def copy(self, support, weight):
        return XaddEngine(self.domain, support, weight, self.mode, self.timeout)

    def get_samples(self, n):
        raise NotImplementedError()

    def __str__(self):
        result = "Xadd:m{}".format(self.mode)
        if self.timeout is not None:
            result += ":t{}".format(self.timeout)
        return result
