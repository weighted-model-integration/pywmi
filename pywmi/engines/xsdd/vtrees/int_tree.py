"""
int_tree.py - An integration tree can be used to represent a variable ordering in tree form. This is referred to as a
pseudo tree in the literature of Variable Elimination and AND/OR graphs.

    IntTree - the abstract integration tree
    IntTreeVar - a leaf node of the tree, containing a variable.
    IntTreeLine - a node in the tree with one child, also contains a variable which can only be eliminated after the
        variables of the child.
    IntTreeSplit - an intermediate node of the tree which has two children, also contains a variable which can only be
        eliminated after the variables of the children.
    IntTreeParallel - an intermediate node of the tree which can have multiple children, also contains a variable which
        can only be eliminated after the variables of all the children.
"""
import math
from abc import ABC, abstractmethod
from typing import List, Tuple, Set, Optional
from pywmi.engines.xsdd.vtrees.vtree import Vtree, VtreeSplit

from .primal import PrimalGraph


class IntTree(ABC):
    """
    Integration tree representing a variable ordering in tree form.
    """

    @abstractmethod
    def con_count(self) -> int:
        """ The amount of continuous variables present in this Integration order tree. """
        pass

    @abstractmethod
    def get_con_vars(self) -> set:
        """ Get all the continuous variables in this tree. """
        pass

    @abstractmethod
    def depth(self) -> int:
        """ Get the maximum depth of this tree (amount of nodes till the leaf, including the leaf and this node) """
        pass

    @abstractmethod
    def create_vtree(self, literals: set, logic2cont) -> Vtree:
        """ Create a vtree that respects the integration order of this tree. """
        pass


class IntTreeVar(IntTree):
    """
    IntTreeVar - a leaf node of the tree, containing a variable.
    """

    def __init__(self, var):
        """
        Create a leaf node of an integration tree containing a variable
        :param var: The variable to associate with this node of the tree. Can not be None.
        """
        assert var is not None
        self.var = var

    def con_count(self):
        return 1

    def get_con_vars(self):
        return {self.var}

    def depth(self):
        return 1

    def create_vtree(self, literals: set, logic2cont):
        literals_map = [(lit, logic2cont[lit]) for lit in literals]
        exists_nonvar = any((self.var not in c_set for (lit, c_set) in literals_map))

        if exists_nonvar:
            # Throw all non 'var' literals in one partition and all 'var' literals in the other.
            vtree_left = Vtree.create_balanced(
                [lit for (lit, c_set) in literals_map if self.var not in c_set], True
            )
            vtree_right = Vtree.create_balanced(
                [lit for (lit, c_set) in literals_map if self.var in c_set], True
            )
            return VtreeSplit(vtree_left, vtree_right)
        else:
            # If no non 'vars', balance out all literals
            return Vtree.create_balanced(list(literals), True)


class IntTreeSplit(IntTree):
    """
    IntTreeSplit - an intermediate node of the tree which has two children. contains a variable which can only be
        eliminated after the variables of the children.
    """

    def __init__(self, var, left: IntTree, right: IntTree):
        """
        Create a node in the Integration tree that connects two children.
        :param var: The variable to associate with this node of the tree. Can be None.
        :param left: The left child of this node. Can not be None.
        :param right: The right child of this node. Can not be None.
        """
        assert left is not None
        assert right is not None
        self.var = var
        self.left = left
        self.right = right

    def con_count(self):
        return (
            int(self.var is not None) + self.left.con_count() + self.right.con_count()
        )

    def get_con_vars(self):
        if self.var is None:
            return self.left.get_con_vars() | self.right.get_con_vars()
        else:
            return {self.var} | self.left.get_con_vars() | self.right.get_con_vars()

    def depth(self):
        return 1 + max(self.left.depth(), self.right.depth())

    def create_vtree(self, literals: set, logic2cont):
        literals_map = [(lit, logic2cont[lit]) for lit in literals]

        # Divide all literals, without self.vars in cont-set, with left-cont in left and right-cont in right
        # Balance out the remaining variables (both with and without self.vars in cont-set)
        left_cons = self.left.get_con_vars()
        right_cons = self.right.get_con_vars()
        left_literals = []
        right_literals = []
        # var_literals = {}  # TODO: Ensure splitting var_literals
        remaining_literals = []
        for (lit, c_set) in literals_map:
            # if self.var in c_set:
            #     remaining_literals.append(lit)
            #     #var_literals |= lit
            #     continue
            in_left = len(c_set & left_cons) > 0
            in_right = len(c_set & right_cons) > 0
            assert (
                not in_left or not in_right
            ), f"Left: {c_set & left_cons} and Right: {c_set & right_cons}"

            if in_left:
                left_literals.append(lit)
            elif in_right:
                right_literals.append(lit)
            else:
                remaining_literals.append(lit)

        # Equally Divide the remaining_variables
        if len(remaining_literals) > 0:
            if len(left_literals) < len(right_literals):
                too_little, too_many = left_literals, right_literals
            else:
                too_little, too_many = right_literals, left_literals
            needed_to_balance = min(
                len(too_many) - len(too_little), len(remaining_literals)
            )
            too_little.extend(remaining_literals[:needed_to_balance])
            del remaining_literals[:needed_to_balance]

            if len(remaining_literals) > 0:
                # Divide the remaining variables equally
                add_to_left = math.floor(len(remaining_literals) / 2)
                left_literals.extend(remaining_literals[:add_to_left])
                right_literals.extend(remaining_literals[add_to_left:])

        return VtreeSplit(
            self.left.create_vtree(set(left_literals), logic2cont),
            self.right.create_vtree(set(right_literals), logic2cont),
        )


class IntTreeParallel(IntTree):
    """
    An Integration tree node with one or more children. The variable can be None.
    When creating a vtree, the children are partitioned into two balanced sets which are stored as the children of an
    IntTreeSplit. The constructor requires the user to provide a weight for each tree. This weight is used in the
    balancing of the two sets.
    """

    def __init__(self, var, trees: List[IntTree], weights=None):
        """
        An Integration tree node with one or more children.
        :param var: The variable in this node. Can be None.
        :param trees: The integration trees that are split in parallel. The list must contains at least 1 element.
        :param weights: Used to create a vtree. The partitioning of the trees will try to balance the weights.
        If weights is None, the weights are based on the amount of literals in that tree.
        :type weights: list[int] | None
        """
        assert trees is not None and len(trees) > 0
        assert weights is None or len(weights) == len(trees)
        self.var = var
        self.trees = trees
        self.weights = weights

    def con_count(self):
        return int(self.var is not None) + sum(tree.con_count() for tree in self.trees)

    def get_con_vars(self):
        if self.var is None:
            return set().union(*(tree.get_con_vars() for tree in self.trees))
        else:
            return {self.var}.union(*(tree.get_con_vars() for tree in self.trees))

    def depth(self):
        return 1 + max(tree.depth() for tree in self.trees)

    def create_vtree(self, literals: set, logic2cont):
        assert len(self.trees) > 0
        if len(self.trees) == 1:
            return self.trees[0].create_vtree(literals, logic2cont)
        elif len(self.trees) == 2:
            return IntTreeSplit(self.var, self.trees[0], self.trees[1]).create_vtree(
                literals, logic2cont
            )
        else:
            # Create balanced partitioning of trees based on the amount of literals in each tree.
            cont_literal_vars = [logic2cont.get(literal) for literal in literals]
            cont_tree_vars = [tree.get_con_vars() for tree in self.trees]

            # Collect weights
            weights = self.weights
            if weights is None:

                def get_lit_count(conts_tree):
                    return sum(
                        len(cont_vars & conts_tree) != 0
                        for cont_vars in cont_literal_vars
                    )

                weights = [get_lit_count(conts_tree) for conts_tree in cont_tree_vars]

            # Partition
            values = list(zip(weights, self.trees))
            left_partition, right_partition = self._partition_trees(values)

            left_trees = [tree for w, tree in left_partition]
            left_weights = [w for w, tree in left_partition]
            left_parallel_tree = IntTreeParallel(None, left_trees, left_weights)

            right_trees = [tree for w, tree in right_partition]
            right_weights = [w for w, tree in right_partition]
            right_parallel_tree = IntTreeParallel(None, right_trees, right_weights)

            # Recursively solve
            split = IntTreeSplit(self.var, left_parallel_tree, right_parallel_tree)
            return split.create_vtree(literals, logic2cont)

    def _partition_trees(
        self, values: List[Tuple[int, IntTree]]
    ) -> Tuple[List[Tuple[int, IntTree]], List[Tuple[int, IntTree]]]:
        """
        Partitions the given trees (values) in two roughly balanced sets.
        Greedy algorithm from https://en.wikipedia.org/wiki/Partition_problem.
        "This greedy approach is known to give a ​7⁄6-approximation to the optimal solution of the optimization version;
        that is, if the greedy algorithm outputs two sets A and B, then max(∑A, ∑B) ≤ 7/6 OPT,
        where OPT is the size of the larger set in the best possible partition."
        :param values: The list of trees to partition. Each element in this list is a tuple of the weight and tree.
        The weight is used in the 'roughly balanced' part.
        :return: A partitioning of the trees in two balanced sets (greedy heuristic).
        """
        left_partition = []
        right_partition = []
        left_weight = 0
        right_weight = 0
        for x in sorted(values, reverse=True, key=lambda x: x[0]):
            if left_weight < right_weight:
                left_partition.append(x)
                left_weight += x[0]
            else:
                right_partition.append(x)
                right_weight += x[0]
        return left_partition, right_partition


class IntTreeLine(IntTree):
    """
    IntTreeLine - a node in the tree with one child, also contains a variable which can only be eliminated
    after the variables of the child.
    """

    def __init__(self, var, line: IntTree):
        """
        Create an integration node with one child (line). This denotes the given variable must be eliminated after
        the variables in the child.
        :param var: The variable to associate with this node. Can not be None.
        :param line: The child in the tree.
        """
        assert var is not None
        assert line is not None
        self.var = var
        self.line = line

    def con_count(self):
        return int(self.var is not None) + self.line.con_count()

    def get_con_vars(self):
        return {self.var} | self.line.get_con_vars()

    def depth(self):
        return 1 + self.line.depth()

    def create_vtree(self, literals: set, logic2cont):
        literals_map = [(lit, logic2cont[lit]) for lit in literals]

        lower_cont = self.line.get_con_vars()
        left_literals = []
        right_literals = []
        for (lit, c_set) in literals_map:
            if len(lower_cont & c_set) == 0:
                left_literals.append(lit)
            else:
                right_literals.append(lit)

        if len(left_literals) != 0 and len(right_literals) != 0:
            vtree_left = Vtree.create_balanced(left_literals, True)
            vtree_right = self.line.create_vtree(set(right_literals), logic2cont)
            return VtreeSplit(vtree_left, vtree_right)
        else:
            return self.line.create_vtree(literals, logic2cont)


class IntTreeFactory:
    """ Factory used to construct a balanced integration tree (IntTree) """

    def __init__(self, graph: PrimalGraph):
        assert graph is not None
        """ The primal graph at the beginning of the process, displaying all the interactions between the variables. """
        self.connected_to = {
            node: targets.copy() for node, targets in graph.connected_to.items()
        }
        # Store integration tree roots with the variables that occur within each root and the height of each root.
        self.roots = []  # type: List[Tuple[IntTree, Set[any], int]]

    def add_node(self, node):
        """ Add the given node (variable) of the primal graph to the integration tree. """
        assert node is not None
        # Root x (index) is relevant if any of the neighbors of node are present in x.
        neighbors = self.connected_to[node]
        connected_root_indices = [
            index
            for index, (tree, conts, height) in enumerate(self.roots)
            if any(neighbor in conts for neighbor in neighbors)
        ]  # TODO: if neighbors & conts != empty?

        # Connect node to roots
        if len(connected_root_indices) == 0:  #  leaf
            self.roots.append((IntTreeVar(node), {node}, 1))

        elif len(connected_root_indices) == 1:  # line
            index = connected_root_indices[0]
            curr_tree, conts, height = self.roots[index]
            conts.add(node)
            new_tree = IntTreeLine(node, curr_tree)
            self.roots[index] = new_tree, conts, height + 1

        elif len(connected_root_indices) == 2:  # split
            i1, i2 = min(connected_root_indices), max(connected_root_indices)
            curr_tree1, conts, height1 = self.roots[i1]
            curr_tree2, conts2, height2 = self.roots[i2]
            conts.update(conts2)
            conts.add(node)
            new_tree = IntTreeSplit(node, curr_tree1, curr_tree2)
            new_height = max(height1, height2) + 1
            self.roots[i1] = new_tree, conts, new_height
            self.roots.pop(i2)

        else:  # parallel
            new_cont = set().union(
                *(self.roots[index][1] for index in connected_root_indices)
            )
            new_cont.add(node)
            trees = [self.roots[index][0] for index in connected_root_indices]
            new_tree = IntTreeParallel(node, trees)
            new_height = (
                max(self.roots[index][2] for index in connected_root_indices) + 1
            )
            connected_root_indices.sort()  # Required because indices change if deleted in improper order
            self.roots[connected_root_indices[0]] = new_tree, new_cont, new_height
            # Clear other roots
            for index in reversed(connected_root_indices[1:]):
                self.roots.pop(index)

    def get_int_tree(self) -> Optional[IntTree]:
        """ Get the current roots as one integration tree. """
        if len(self.roots) == 0:
            return None
        elif len(self.roots) == 1:
            return self.roots[0][0]
        elif len(self.roots) == 2:
            return IntTreeSplit(None, self.roots[0][0], self.roots[1][0])
        else:
            trees = list(map(lambda x: x[0], self.roots))
            return IntTreeParallel(None, trees)

    def get_least_depth_increase(self, nodes: List[any]) -> List[any]:
        """ Of all nodes, returns the ones that increases the depth of the roots the least """
        if len(nodes) == 1:
            return nodes

        min_height = math.inf
        min_height_nodes = []
        # Go over all nodes, compute height and store the ones with the minimum height.
        for node in nodes:
            height = self.get_new_height(node)
            if min_height == height:
                min_height_nodes.append(node)
            elif min_height > height:
                min_height = height
                min_height_nodes = [node]
        return min_height_nodes

    def current_depth(self) -> int:
        """ The depth of the integration tree if it was formed now (get_int_tree()). """
        if len(self.roots) == 1:
            return self.roots[0][2]
        else:
            return max(root[2] for root in self.roots) + 1

    def get_new_height(self, node) -> int:
        """ The new height of an integration root when node was to be added. """
        assert node is not None
        # Root x (index) is relevant if any of the neighbors of node are present in x.
        neighbors = self.connected_to[node]
        connected_root_indices = [
            index
            for index, (tree, conts, height) in enumerate(self.roots)
            if any(neighbor in conts for neighbor in neighbors)
        ]

        # new root
        if len(connected_root_indices) == 0:
            return 1
        # extend line
        elif len(connected_root_indices) == 1:
            _, _, height = self.roots[connected_root_indices[0]]
            return height + 1
        # create split
        elif len(connected_root_indices) == 2:
            i1, i2 = connected_root_indices[0], connected_root_indices[1]
            _, _, height1 = self.roots[i1]
            _, _, height2 = self.roots[i2]
            return max(height1, height2) + 1
        # Create multiple parallel
        else:
            return max(self.roots[index][2] for index in connected_root_indices) + 1
