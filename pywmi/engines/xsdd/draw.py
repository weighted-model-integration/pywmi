import subprocess

from pywmi.engines.xsdd.literals import LiteralInfo
from pywmi.engines.xsdd.semiring import SddWalker, walk
from pywmi.temp import TemporaryFile

import pysmt.shortcuts as smt


class SddToDot(SddWalker):
    def __init__(
        self,
        literals: LiteralInfo,
        node_annotations=None,
        edge_annotations=None,
        skip_false=False,
    ):
        self.literals = literals
        # self.reverse_abstractions = {v: k for k, v in abstractions.items()}
        # self.lit_to_var = {v: k for k, v in var_to_lit.items()}
        self.vertex_counter = 0
        self.node_annotations = node_annotations or dict()
        self.edge_annotations = edge_annotations or dict()
        self.seen = set()
        self.skip_false = skip_false

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
        return (
            vertex_id,
            {'{} [label="{}",color=black];'.format(vertex_id, label)},
            set(),
            node.id,
        )

    def walk_false(self, node):
        vertex_id = self.get_id(node.id)
        label = "false"
        if node.id in self.node_annotations:
            label += ": {}".format(self.node_annotations[node.id])
        if self.skip_false:
            nodes = set()  # Using nodes = {} to denote value = false
        else:
            nodes = {'{} [label="{}",color=black];'.format(vertex_id, label)}
        return (
            vertex_id,
            nodes,
            set(),
            node.id,
        )

    def walk_and(self, prime_result, sub_result, prime_node, sub_node):
        key = (prime_node.id, sub_node.id)
        vertex_id = self.get_id(key)
        label = "AND"
        if key in self.node_annotations:
            label += ": {}".format(self.node_annotations[key])

        label_prime = self.edge_annotations.get((key, prime_result[3]), "")
        label_sub = self.edge_annotations.get((key, sub_result[3]), "")
        if self.skip_false and (len(prime_result[1]) == 0 or len(sub_result[1]) == 0):
            # This means we skipping false and the result of AND was false.
            nodes = set()
            edges = set()
        else:
            nodes = (
                prime_result[1]
                | sub_result[1]
                | {'{} [label="{}",color=black];'.format(vertex_id, label)}
            )
            edges = (
                prime_result[2]
                | sub_result[2]
                | {
                    '{} -> {} [label="{}"];'.format(
                        vertex_id, prime_result[0], label_prime
                    ),
                    '{} -> {} [label="{}"];'.format(
                        vertex_id, sub_result[0], label_sub
                    ),
                }
            )
        return (
            vertex_id,
            nodes,
            edges,
            key,
        )

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
        nodes.add('{} [label="{}",color=black];'.format(vertex_id, label))
        for child_result in child_results:
            if not self.skip_false or len(child_result[1]) > 0:
                label = self.edge_annotations.get((node.id, child_result[3]), "")
                edges.add(
                    '{} -> {} [label="{}"];'.format(vertex_id, child_result[0], label)
                )
        return vertex_id, nodes, edges, node.id

    def walk_literal(self, l, node):
        vertex_id = self.get_id(node.id)
        if self.literals.is_number_boolean(l):
            label = "[{}] {}".format(
                node.id, ("~" if l < 0 else "") + str(self.literals.number_to_val(l))
            )
            if node.id in self.node_annotations:
                label += ": {}".format(self.node_annotations[node.id])
            return (
                vertex_id,
                {
                    '{} [label="{}",color=black,shape=rectangle];'.format(
                        vertex_id, label
                    )
                },
                set(),
                node.id,
            )
        else:
            inequality = self.literals.number_to_val(l)
            if l < 0:
                inequality = smt.simplify(~inequality)
            label = "[{}] {}".format(node.id, str(inequality))
            if node.id in self.node_annotations:
                label += ": {}".format(self.node_annotations[node.id])
            return (
                vertex_id,
                {
                    '{} [label="{}",color=black,shape=rectangle];'.format(
                        vertex_id, label
                    )
                },
                set(),
                node.id,
            )


def sdd_to_dot(
    diagram,
    literals: LiteralInfo,
    node_annotations=None,
    edge_annotations=None,
    draw_false=True,
):
    walker = SddToDot(
        literals, node_annotations, edge_annotations, skip_false=not draw_false
    )
    _, nodes, edges, _node_id = walk(walker, diagram)
    return "digraph G {{\n{}\n{}\n}}".format("\n".join(nodes), "\n".join(edges))


def sdd_to_png_file(
    diagram,
    literals: LiteralInfo,
    filename,
    node_annotations=None,
    edge_annotations=None,
    draw_false=True,
):
    if not filename.endswith(".png"):
        filename = filename + ".png"

    with TemporaryFile() as f:
        with open(f, "w") as ref:
            print(
                sdd_to_dot(
                    diagram,
                    literals,
                    node_annotations,
                    edge_annotations,
                    draw_false=draw_false,
                ),
                file=ref,
            )
        subprocess.call(["dot", "-Tpng", f, "-o", filename])


def sdd_to_dot_file(
    diagram,
    literals: LiteralInfo,
    filename,
    node_annotations=None,
    edge_annotations=None,
    draw_false=True,
):
    if not filename.endswith(".dot"):
        filename = filename + ".dot"
    with open(filename, "w") as ref:
        print(
            sdd_to_dot(
                diagram,
                literals,
                node_annotations,
                edge_annotations,
                draw_false=draw_false,
            ),
            file=ref,
        )
