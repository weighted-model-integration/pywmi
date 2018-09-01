import numpy as np

from .domain import Domain, export_domain, import_domain
from .parse import nested_to_smt, smt_to_nested, combined_nested_to_wmi
from .smt_check import evaluate, evaluate_assignment
from .smt_walk import SmtWalker
from .engines.rejection import RejectionEngine
from .engines.pa import PredicateAbstractionEngine
from .engines.xadd import XaddEngine
from .engine import Engine


def _change_polytope():
    import polytope

    def _get_patch(poly1, **kwargs):
        import matplotlib as mpl
        V = polytope.extreme(poly1)
        rc, xc = polytope.cheby_ball(poly1)
        x = V[:, 1] - xc[1]
        y = V[:, 0] - xc[0]
        mult = np.sqrt(x ** 2 + y ** 2)
        x = x / mult
        angle = np.arccos(x)
        corr = np.ones(y.size) - 2 * (y < 0)
        angle = angle * corr
        ind = np.argsort(angle)
        # create patch
        patch = mpl.patches.Polygon(V[ind, :], True, **kwargs)
        patch.set_zorder(0)
        return patch

    def _newax(ax=None):
        """Add subplot to current figure and return axes."""
        from matplotlib import pyplot as plt
        if ax is not None:
            return ax
        fig = plt.figure()
        ax = fig.add_subplot(1, 1, 1)
        return ax

    def _plot(self, ax=None, color=None,
             hatch=None, alpha=1.0):
        if self.dim != 2:
            raise Exception("Cannot plot polytopes of dimension larger than 2")
        ax = _newax(ax)
        if not polytope.is_fulldim(self):
            return None
        if color is None:
            color = np.random.rand(3)
        poly = _get_patch(
            self, facecolor=color, hatch=hatch, alpha=alpha)
        ax.add_patch(poly)
        return ax

    polytope.Polytope.plot = _plot


_change_polytope()