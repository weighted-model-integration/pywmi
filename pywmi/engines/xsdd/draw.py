import subprocess

from pywmi.engines.xsdd.semiring import SddWalker, walk
import pysmt.shortcuts as smt

from pywmi.util import TemporaryFile


class SddToDot(SddWalker):
    def __init__(self, literals, node_annotations=None, edge_annotations=None):
        self.literals = literals
        self.vertex_counter = 0
        self.node_annotations = node_annotations or dict()
        self.edge_annotations = edge_annotations or dict()
        self.seen = set()

    def get_id(self, key):
        # assert key not in self.seen
        self.seen.add(key)
        vertex_id = self.vertex_counter
        self.vertex_counter += 1
        return vertex_id

    def walk_true(self, node):
        vertex_id = self.get_id(node.id)
        label = "true"
        if node.id in self.node_annotations:
            label += ": {}".format(self.node_annotations[node.id])
        return vertex_id, {
            "{} [label=\"{}\",color=black];".format(vertex_id, label)
        }, set(), node.id

    def walk_false(self, node):
        vertex_id = self.get_id(node.id)
        label = "false"
        if node.id in self.node_annotations:
            label += ": {}".format(self.node_annotations[node.id])

        return vertex_id, {
            "{} [label=\"{}\",color=black];".format(vertex_id, label)
        }, set(), node.id

    def walk_and(self, prime_result, sub_result, prime_node, sub_node):
        key = (prime_node.id, sub_node.id)
        vertex_id = self.get_id(key)
        label = "AND"
        if key in self.node_annotations:
            label += ": {}".format(self.node_annotations[key])

        label_prime = self.edge_annotations.get((key, prime_result[3]), "")
        label_sub = self.edge_annotations.get((key, sub_result[3]), "")

        return vertex_id, prime_result[1] | sub_result[1] | {
            "{} [label=\"{}\",color=black];".format(vertex_id, label)
        }, prime_result[2] | sub_result[2] | {
            "{} -> {} [label=\"{}\"];".format(vertex_id, prime_result[0], label_prime),
            "{} -> {} [label=\"{}\"];".format(vertex_id, sub_result[0], label_sub),
        }, key

    def walk_or(self, child_results, node):
        vertex_id = self.get_id(node.id)
        nodes = set()
        edges = set()
        label = "[{}] OR".format(node.id)
        if node.id in self.node_annotations:
            label += ": {}".format(self.node_annotations[node.id])
        for child_result in child_results:
            nodes |= child_result[1]
            edges |= child_result[2]
        nodes.add("{} [label=\"{}\",color=black];".format(vertex_id, label))
        for child_result in child_results:
            label = self.edge_annotations.get((node.id, child_result[3]), "")
            edges.add("{} -> {} [label=\"{}\"];".format(vertex_id, child_result[0], label))
        return vertex_id, nodes, edges, node.id

    def walk_literal(self, l, node):
        vertex_id = self.get_id(node.id)
        abstraction = self.literals[self.literals.inv_numbered[abs(l)]]
        if isinstance(abstraction, str):
            label = "[{}] {}".format(node.id, ("~" if l < 0 else ("" + abstraction)))
            if node.id in self.node_annotations:
                label += ": {}".format(self.node_annotations[node.id])
            return vertex_id, {
                "{} [label=\"{}\",color=black,shape=rectangle];".format(vertex_id, label)
            }, set(), node.id
        else:
            if l < 0:
                abstraction = smt.simplify(~abstraction)
            label = "[{}] {}".format(node.id, str(abstraction))
            if node.id in self.node_annotations:
                label += ": {}".format(self.node_annotations[node.id])
            return vertex_id, {
                "{} [label=\"{}\",color=black,shape=rectangle];".format(vertex_id, label)
            }, set(), node.id


def sdd_to_dot(diagram, literals, node_annotations=None, edge_annotations=None):
    walker = SddToDot(literals, node_annotations, edge_annotations)
    _, nodes, edges, _node_id = walk(walker, diagram)
    return "digraph G {{\n{}\n{}\n}}".format("\n".join(nodes), "\n".join(edges))


def sdd_to_png_file(diagram, literals, filename, node_annotations=None, edge_annotations=None):
    if not filename.endswith(".png"):
        filename = filename + ".png"

    with TemporaryFile() as f:
        with open(f, "w") as ref:
            print(sdd_to_dot(diagram, literals, node_annotations, edge_annotations), file=ref)
        subprocess.call(["dot", "-Tpng", f, "-o", filename])


def sdd_to_dot_file(diagram, literals, filename, node_annotations=None, edge_annotations=None):
    if not filename.endswith(".dot"):
        filename = filename + ".dot"
    with open(filename, "w") as ref:
        print(sdd_to_dot(diagram, literals, node_annotations, edge_annotations), file=ref)
