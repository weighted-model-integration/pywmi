from .core import InternalNode, TerminalNode
from .walk import WalkingProfile, ParentsWalker


def to_dot(diagram, pretty=None, print_node_ids=False):
    if pretty is None:
        pretty = False

    layers = WalkingProfile.extract_layers(diagram, ParentsWalker(diagram).walk())
    string = "digraph G {\n"
    string += "\trankdir = TB;\n"
    for i in layers:
        for node_id in layers[i]:
            node = diagram.node(node_id)
            if isinstance(node, InternalNode):
                label = str(node.decision) if pretty else repr(node.decision)
                if print_node_ids:
                    label = "{}: {}".format(node_id, label)
                shape = ""
            elif isinstance(node, TerminalNode):
                expression = str(node.expression)
                try:
                    exp_float = float(expression)
                    if int(exp_float) == exp_float:
                        expression = str(int(exp_float))
                except ValueError:
                    pass
                label = expression if not print_node_ids else "{}: {}".format(node_id, expression)
                shape = "box"
            else:
                raise RuntimeError("Unexpected node type: {}".format(type(node)))
            string += "\t{} [label=\"{}\", shape=\"{}\"]\n".format(node_id, label, shape)
            if isinstance(node, InternalNode):
                string += "\t{} -> {}\n".format(node_id, node.child_true)
                string += "\t{} -> {} [style=dashed]\n".format(node_id, node.child_false)
        string += "\t{{rank = same; {}}}\n".format(" ".join(map(lambda n: str(n) + ";", layers[i])))
    string += "}\n"
    return string


def export(diagram, filename, pretty=None, print_node_ids=False):
    with open(filename, "w") as file:
        file.write(to_dot(diagram, pretty=pretty, print_node_ids=print_node_ids))
