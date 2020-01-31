"""
    primal.py - A structure to represent the interactions between several variables (nodes), and quickly compute the
    min-fills/min degrees and process the removal of a node.
"""
import math
from typing import List, Tuple, Dict, Set, Iterable
from sortedcollections import ValueSortedDict


class PrimalGraph:
    """ Nodes should not be connected to themselves. """

    def __init__(self, vertices: Iterable[any], compute_fills=True, compute_degrees=True):
        """
        Create a Primal graph representing the interactions between vertices.
        For min-fill or min-induced-width, use remove_and_process_node() instead of use remove_node()
        :param vertices: The vertices of the graph
        :param compute_fills; Whether this will be used to compute fills.
        :param compute_degrees: Whether this will be used to compute degrees.
        """
        self.connected_to: Dict[any, Set[any]] = {vertex: set() for vertex in vertices}
        self._fills: ValueSortedDict[any, Tuple[int, List[Tuple[any, Set[any]]]]] = ValueSortedDict(lambda n: n[0]) if \
            compute_fills else None
        self._degrees: ValueSortedDict[any, int] = ValueSortedDict() if compute_degrees else None

    def nb_fills(self):
        """ The amount of vertices for which their fills are stored. """
        assert self._fills is not None
        return len(self._fills)

    def nb_degrees(self):
        """ The amount of vertices for which their degrees are stored. """
        assert self._degrees is not None
        return len(self._degrees)

    def add_edge(self, a, b):
        """ Add edge between a and b. """
        assert a != b
        self.connected_to[a].add(b)
        self.connected_to[b].add(a)

    def add_edges(self, node_set: Set[any]):
        """ Add edges between all the nodes in the node_set. """
        for node in node_set:
            self.connected_to[node].update(node_set)
            self.connected_to[node].discard(node)

    def compute_fills(self, of_nodes=None):
        """ Compute the minfill values for each vertex in of_nodes or all vertices if of_nodes is None. """
        assert self._fills is not None
        if of_nodes is None:
            of_nodes = self.connected_to.keys()

        for vertex in of_nodes:
            connections = self.connected_to.get(vertex)
            fill = 0
            edges = []
            for connected_vertex in connections:
                # Get all vertices that we still need to connect connected_vertex to when vertex is removed.
                unconnected = connections - self.connected_to[connected_vertex]
                unconnected.discard(connected_vertex)
                if len(unconnected) > 0:
                    fill += len(unconnected)
                    edges.append((connected_vertex, unconnected))
            self._fills[vertex] = (fill, edges)

    def compute_degrees(self, of_nodes=None):
        """ Compute the degrees for each vertex in of_nodes or all vertices if of_nodes is None. """
        assert self._degrees is not None
        if of_nodes is None:
            of_nodes = self.connected_to.keys()

        for vertex in of_nodes:
            self._degrees[vertex] = len(self.connected_to[vertex])

    def remove_and_process_node(self, a):
        """ Remove node a, connect each of its neighbors with each other and recompute minfills """
        # remove node
        neighbors = self.connected_to.pop(a)

        # connect neighbors
        if self._fills is not None:
            _, edges = self._fills.pop(a)
            for neighbor in neighbors:
                self.connected_to[neighbor].discard(a)
            for vertex, new_targets in edges:
                self.connected_to[vertex] |= new_targets
            self.compute_fills(neighbors)  # recompute fills
        else:
            for neighbor in neighbors:
                self.connected_to[neighbor] |= neighbors
                self.connected_to[neighbor].discard(a)

        # Compute degrees
        if self._degrees is not None:
            self.compute_degrees(neighbors)

    def remove_node(self, a):
        """ Remove all connections from and to node a. """
        # Remove connection
        neighbors = self.connected_to.pop(a)
        for neighbor in neighbors:
            self.connected_to[neighbor].discard(a)
        # Recompute degrees
        if self._degrees is not None:
            self.compute_degrees(neighbors)
        # Recompute fills
        if self._fills is not None:
            self._fills.pop(a)
            self.compute_fills(neighbors)

    def get_minfills(self) -> List[any]:
        """ Get all vertices with the minimum nb of fills. """
        assert self._fills is not None and len(self._fills) > 0
        _, (minfill, _) = self._fills.peekitem(0)
        endIndex = len(self._fills)
        for index, (fill, edges) in enumerate(self._fills.values()):
            if fill != minfill:
                endIndex = index
                break
        return list(self._fills.keys())[:endIndex]

    def get_mindegrees(self) -> List[any]:
        """ Get all vertices with the minimum degree """
        assert self.nb_degrees() > 0
        _, mindegree = self._degrees.peekitem(0)
        endIndex = len(self._degrees)
        for index, degree in enumerate(self._degrees.values()):
            if degree != mindegree:
                endIndex = index
                break
        return list(self._degrees.keys())[:endIndex]

    def get_lowest_future_minfill(self, vertices) -> List[any]:
        """ Get the subset of vertices which, when removed, result in the lowest next minfill. """
        if len(vertices) == 1:
            return vertices

        lowest_minfill = math.inf
        lowest_minfill_vertices = []
        for vertex in vertices:
            neighbors = self.connected_to[vertex]

            # Backup
            connected_to_partial_backup = {neighbor: self.connected_to[neighbor].copy() for neighbor in neighbors}
            connected_to_partial_backup[vertex] = neighbors
            fills_partial_backup = {neighbor: self._fills[neighbor] for neighbor in neighbors}
            fills_partial_backup[vertex] = self._fills[vertex]

            # Compute
            self.remove_and_process_node(vertex)
            _, (new_minfill, _) = self._fills.peekitem(0)
            if new_minfill < lowest_minfill:
                lowest_minfill = new_minfill
                lowest_minfill_vertices = [vertex]
            elif new_minfill == lowest_minfill:
                lowest_minfill_vertices.append(vertex)

            # Restore
            self.connected_to.update(connected_to_partial_backup)
            self._fills.update(fills_partial_backup)

        return lowest_minfill_vertices


def create_interaction_graph_from_literals(vertices: Iterable[any],
                                           co_occurrences: Iterable[Set[any]],
                                           compute_fills: bool,
                                           compute_degrees: bool) -> PrimalGraph:
    """
    Create an interaction graph of the vertices and the given interactions (co-occurrences). This interaction graph
    contains operations to compute the fill edges and degrees.
    :param vertices: The vertices of the graph (e.g. continuous variables)
    :param co_occurrences: Groups of interacting vertices. Every vertex in the group must be in vertices.
    :param compute_fills: Whether the resulting graph should store the fill edges.
    :param compute_degrees: Wheteher the resulting graph should store the vertex degrees (nb of edges).
    :return: An interaction graph (V,E) with V = vertices and (x,y) in E iff x and y occur in a co-occurrence group.
    """
    primal = PrimalGraph(vertices, compute_fills=compute_fills, compute_degrees=compute_degrees)
    for co_occurrence_set in co_occurrences:
        primal.add_edges(co_occurrence_set)
    return primal
