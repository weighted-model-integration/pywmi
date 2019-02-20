import subprocess

from pywmi.engines.xsdd.semiring import SddWalker, walk
import pysmt.shortcuts as smt

from pywmi.temp import TemporaryFile


class SddToDot(SddWalker):
    def __init__(self, abstractions, var_to_lit, node_annotations=None, edge_annotations=None):
        self.reverse_abstractions = {v: k for k, v in abstractions.items()}
        self.lit_to_var = {v: k for k, v in var_to_lit.items()}
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
        if abs(l) in self.lit_to_var:
            label = "[{}] {}".format(node.id, ("~" if l < 0 else "") + str(self.lit_to_var[abs(l)]))
            if node.id in self.node_annotations:
                label += ": {}".format(self.node_annotations[node.id])
            return vertex_id, {
                "{} [label=\"{}\",color=black,shape=rectangle];".format(vertex_id, label)
            }, set(), node.id
        else:
            inequality = self.reverse_abstractions[abs(l)]
            if l < 0:
                inequality = smt.simplify(~inequality)
            label = "[{}] {}".format(node.id, str(inequality))
            if node.id in self.node_annotations:
                label += ": {}".format(self.node_annotations[node.id])
            return vertex_id, {
                "{} [label=\"{}\",color=black,shape=rectangle];".format(vertex_id, label)
            }, set(), node.id


def sdd_to_dot(diagram, abstractions, var_to_lit, node_annotations=None, edge_annotations=None):
    walker = SddToDot(abstractions, var_to_lit, node_annotations, edge_annotations)
    _, nodes, edges, _node_id = walk(walker, diagram)
    return "digraph G {{\n{}\n{}\n}}".format("\n".join(nodes), "\n".join(edges))


def sdd_to_png_file(diagram, abstractions, var_to_lit, filename, node_annotations=None, edge_annotations=None):
    if not filename.endswith(".png"):
        filename = filename + ".png"

    with TemporaryFile() as f:
        with open(f, "w") as ref:
            print(sdd_to_dot(diagram, abstractions, var_to_lit, node_annotations, edge_annotations), file=ref)
        subprocess.call(["dot", "-Tpng", f, "-o", filename])


def sdd_to_dot_file(diagram, abstractions, var_to_lit, filename, node_annotations=None, edge_annotations=None):
    if not filename.endswith(".dot"):
        filename = filename + ".dot"
    with open(filename, "w") as ref:
        print(sdd_to_dot(diagram, abstractions, var_to_lit, node_annotations, edge_annotations), file=ref)
