from .core import InternalNode, TerminalNode, DefaultCache, Pool, Diagram


class Walker:
    def __init__(self, diagram):
        """
        :param Diagram diagram:
        """
        self._diagram = diagram

    @property
    def diagram(self):
        return self._diagram

    def walk(self):
        """
        Walk the given diagram.
        :return: The result
        """
        raise NotImplementedError()


class DepthFirstWalker(Walker):
    def visit_terminal(self, terminal_node, parent_message):
        """
        Visit a terminal node.
        :param TerminalNode terminal_node: The terminal node to visit
        :param parent_message: The message received from the parent
        :return: The result message to be passed up
        """
        raise NotImplementedError()

    def visit_internal(self, internal_node, parent_message):
        """
        Visit an internal node.
        :param InternalNode internal_node: The internal node to visit
        :param parent_message: The message received from the parent (is None for root)
        :return: A tuple of messages to be passed to the true and false child node respectively
        """
        raise NotImplementedError()

    def walk(self):
        """
        Walks the diagram without computing a result.
        """
        self._visit(self._diagram.root_node)

    def _visit(self, node, message=None):
        if isinstance(node, TerminalNode):
            self.visit_terminal(node, message)
        elif isinstance(node, InternalNode):
            true_message, false_message = self.visit_internal(node, message)
            self._visit(self._diagram.node(node.child_true), true_message)
            self._visit(self._diagram.node(node.child_false), false_message)
        else:
            raise RuntimeError("Unexpected node type {}.".format(type(node)))


class DepthFirstUniqueWalker(DepthFirstWalker):
    def visit_terminal(self, terminal_node, parent_message):
        raise NotImplementedError()

    def visit_internal(self, internal_node, parent_message):
        raise NotImplementedError()

    def __init__(self, diagram):
        DepthFirstWalker.__init__(self, diagram)
        self._seen = None  # type: set

    def walk(self):
        """
        Walks the diagram without computing a result. However, every node is only visited once.
        """
        self._seen = set()
        DepthFirstWalker.walk(self)
        self._seen = None

    def _visit(self, node, message=None):
        if isinstance(node, TerminalNode):
            self.visit_terminal(node, message)
        elif isinstance(node, InternalNode):
            true_message, false_message = self.visit_internal(node, message)
            if node.node_id not in self._seen:
                self._seen.add(node.node_id)
                self._visit(self._diagram.node(node.child_true), true_message)
                self._visit(self._diagram.node(node.child_false), false_message)
        else:
            raise RuntimeError("Unexpected node type {}.".format(type(node)))


class DownUpWalker(Walker):
    def __init__(self, diagram, cache_messages=False):
        Walker.__init__(self, diagram)
        self.cache_messages = cache_messages
        self.message_cache = None

    def visit_terminal(self, terminal_node, parent_message):
        """
        Visit a terminal node.
        :param terminal_node: The terminal node to visit
        :param parent_message: The message received from the parent
        :return: The result message to be passed up
        """
        raise NotImplementedError()

    def visit_internal_down(self, internal_node, parent_message):
        """
        Visit an internal node on the way down.
        :param internal_node: The internal node to visit
        :param parent_message: The message received from the parent
        :return: A tuple of messages to be passed to the true and false child node respectively
        """
        raise NotImplementedError()

    def visit_internal_aggregate(self, internal_node, true_result, false_result):
        """
        Visit an internal node on the way up.
        :param internal_node: The internal node to visit
        :param true_result: The message received from the true child node
        :param false_result: The message received from the false child node
        :return: The message to be passed up
        """
        raise NotImplementedError()

    def walk(self):
        if self.cache_messages:
            self.message_cache = dict()
        result = self._visit(self._diagram.root_node)
        self.message_cache = None
        return result

    def _visit(self, node, message=None):
        def cache_result(result):
            if self.cache_messages:
                self.message_cache[(node, message)] = result
            return result

        if self.cache_messages:
            if (node, message) in self.message_cache:
                return self.message_cache[(node, message)]

        if isinstance(node, TerminalNode):
            return cache_result(self.visit_terminal(node, message))
        elif isinstance(node, InternalNode):
            true_message, false_message = self.visit_internal_down(node, message)
            true_result = self._visit(self._diagram.node(node.child_true), true_message)
            false_result = self._visit(self._diagram.node(node.child_false), false_message)
            return cache_result(self.visit_internal_aggregate(node, true_result, false_result))
        else:
            raise RuntimeError("Unexpected node type {}.".format(type(node)))


class ParentsWalker(DepthFirstUniqueWalker):
    def __init__(self, diagram):
        DepthFirstUniqueWalker.__init__(self, diagram)
        self._nodes = None

    def walk(self):
        self._nodes = {self._diagram.root_node.node_id: set()}
        DepthFirstUniqueWalker.walk(self)
        nodes = self._nodes
        self._nodes = None
        return nodes

    def visit_internal(self, internal_node, parent_message):
        self._update_parents(internal_node, parent_message)
        return internal_node.node_id, internal_node.node_id

    def visit_terminal(self, terminal_node, parent_message):
        self._update_parents(terminal_node, parent_message)

    def _update_parents(self, internal_node, parent):
        if parent is not None:
            if internal_node.node_id not in self._nodes:
                self._nodes[internal_node.node_id] = set()
            if parent in self._nodes[internal_node.node_id]:
                print("Already included as parent...")
            self._nodes[internal_node.node_id].add(parent)


class WalkingProfile:
    def __init__(self, diagram):
        parents = ParentsWalker(diagram).walk()
        counts = {n: len(parents[n]) for n in parents}
        nodes_and_counts = list((n, counts[n]) for n in WalkingProfile.extract_cache(parents, diagram))
        self._nodes = list(n for n, _ in nodes_and_counts)
        self._counts = {n: (c, 0) for n, c in nodes_and_counts}
        self._next = 0

    def __iter__(self):
        return iter(self._nodes)

    def reset(self):
        """
        Resets the profile.
        """
        self._counts = {n: (self._counts[n][0], 0) for n in self._counts}
        self._next = 0

    def count(self, node):
        """
        Increments the counter for the given node. Can be used to keep track of what nodes still have direct parents to
        be visited.
        :param node: The node to be counted
        :return bool: True iff the count is now equal to the number of parents of the given node, else False
        """
        c, i = self._counts[node]
        i += 1
        self._counts[node] = (c, i)
        if i == c:
            return True
        elif i < c:
            return False
        else:
            raise RuntimeError("Count is already saturated")

    def has_next(self):
        """
        :return bool: True iff there is a next node to visit, else False
        """
        return self._next < len(self._nodes)

    def next(self):
        """
        :return int: The id of the next node to visit
        """
        current = self._nodes[self._next]
        self._next += 1
        return current

    @staticmethod
    def extract_cache(parents, diagram):
        nested_reverse = WalkingProfile.extract_layers(diagram, parents)
        reverse_list = []
        for i in range(0, len(nested_reverse)):
            for node_id in nested_reverse[i]:
                reverse_list.append(node_id)
        return reversed(reverse_list)

    @staticmethod
    def extract_layers(diagram, parents):
        root_id = diagram.root_node.node_id
        positions = {root_id: 0}
        watch = [root_id]
        while len(watch) > 0:
            current_id = watch.pop()
            current_parents = parents[current_id]
            if not len(current_parents) == 0:
                raise RuntimeError("Parents not empty, found {}.".format(current_parents))
            current_node = diagram.node(current_id)
            if isinstance(current_node, InternalNode):
                for child_id in (current_node.child_true, current_node.child_false):
                    if child_id not in positions:
                        positions[child_id] = 0
                    parents[child_id].remove(current_id)
                    positions[child_id] = max(positions[child_id], positions[current_id] + 1)
                    if len(parents[child_id]) == 0:
                        watch.append(child_id)
        nested_reverse = dict()
        for node_id in positions:
            count = positions[node_id]
            if count not in nested_reverse:
                nested_reverse[count] = []
            nested_reverse[count].append(node_id)
        return nested_reverse


class BottomUpWalker(Walker):
    def __init__(self, diagram, profile=None):
        Walker.__init__(self, diagram)
        if profile is None:
            profile = get_profile(diagram)
        self._profile = profile

    def visit_terminal(self, terminal_node):
        """
        Visit a bottom terminal node.
        :param terminal_node: The terminal node to visit
        :return: The message to be passed up
        """
        raise NotImplementedError()

    def visit_internal(self, internal_node, true_message, false_message):
        """
        Visit an internal node.
        :param internal_node: The internal node to visit
        :param true_message: The message received from the true child node
        :param false_message: The message received from the false child node
        :return: The message to be passed up
        """
        raise NotImplementedError()

    def walk(self):
        messages = dict()
        while self._profile.has_next():
            node = self._diagram.node(self._profile.next())
            if isinstance(node, TerminalNode):
                messages[node.node_id] = self.visit_terminal(node)
            elif isinstance(node, InternalNode):
                true_message = self._retrieve_message(node.child_true, messages)
                false_message = self._retrieve_message(node.child_false, messages)
                messages[node.node_id] = self.visit_internal(node, true_message, false_message)
            else:
                raise RuntimeError("Unexpected node type {}.".format(type(node)))
        if len(messages) != 1:
            # export(self._diagram, "visual/walk/diagram.dot")
            # print(self._profile)
            raise RuntimeError("Message cache not reduced to 1 ({}).".format(list(messages)))
        root, result = messages.popitem()
        if root != self._diagram.root_node.node_id:
            raise RuntimeError("Remaining node not root.")
        self._profile.reset()
        return result

    def _retrieve_message(self, node_id, messages):
        if self._profile.count(node_id):
            return messages.pop(node_id, None)
        else:
            return messages[node_id]


class TopDownWalker(Walker):
    def __init__(self, diagram):
        Walker.__init__(self, diagram)
        self.parents = ParentsWalker(diagram).walk()

    def visit_internal(self, internal_node, messages):
        """
        Visits an internal node with the list of messages received from its parents.
        :type internal_node: InternalNode
        :type messages: object[]
        :rtype: tuple
        """
        raise NotImplementedError()

    def visit_terminal(self, terminal_node, messages):
        """
        Visits a terminal node with the list of messages received from its parents.
        :type terminal_node: TerminalNode
        :type messages: object[]
        """
        raise NotImplementedError()

    def walk(self):
        enabled = set()
        enabled.add(self.diagram.root_id)
        message_cache = {self.diagram.root_id: []}
        counts = {}

        def count(node_id):
            if node_id not in counts:
                counts[node_id] = 0
            counts[node_id] += 1
            if counts[node_id] == len(self.parents[node_id]):
                enabled.add(node_id)

        def message(node_id, the_message):
            if node_id not in message_cache:
                message_cache[node_id] = []
            message_cache[node_id].append(the_message)

        while len(enabled) > 0:
            current_id = enabled.pop()
            messages = message_cache[current_id]
            node = self.diagram.pool.get_node(current_id)
            if node.is_terminal():
                self.visit_terminal(node, messages)
            else:
                message_true, message_false = self.visit_internal(node, messages)
                count(node.child_true)
                count(node.child_false)
                message(node.child_true, message_true)
                message(node.child_false, message_false)


def profile_cache_is_enabled(pool):
    return pool.has_cache("profile")


def add_profile_cache(pool):
    def construct_walking_profile(p, node):
        return WalkingProfile(p.diagram(node))
    if not profile_cache_is_enabled(pool):
        pool.add_cache("profile", DefaultCache(construct_walking_profile))


def get_profile(root, pool=None):
    if isinstance(root, Diagram):
        pool = root.pool
        root = root.root_id
    assert isinstance(pool, Pool)
    add_profile_cache(pool)
    return pool.get_cached("profile", root)


def profile_exists(root, pool=None):
    if isinstance(root, Diagram):
        pool = root.pool
        root = root.root_id
    assert isinstance(pool, Pool)
    return profile_cache_is_enabled(pool) and pool.is_cached("profile", root)


def walk_leaves(f, root, pool=None):
    """
    Calls the given function f on all leaf nodes of the given diagram
    :param f: The function to run on leaf nodes [(pool, node) -> None]
    :param Diagram|int root: The diagram or root node id
    :param Pool|None pool: If the root is an integer, a pool needs to be provided
    """
    if isinstance(root, Diagram):
        pool = root.pool
        root = root.root_id
    else:
        assert isinstance(pool, Pool)

    profile = get_profile(root, pool=pool)
    assert isinstance(profile, WalkingProfile)
    while profile.has_next():
        node = pool.get_node(profile.next())
        if isinstance(node, TerminalNode):
            f(pool, node)
    profile.reset()


def map_leaves(f, root, pool=None):
    result = []

    def wrap(p, n):
        result.append(f(p, n))

    walk_leaves(wrap, root, pool=pool)
    return result
