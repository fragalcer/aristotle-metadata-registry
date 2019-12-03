from aristotle_mdr.utils.text import truncate_words
from typing import Optional, List, Dict, Tuple, Any, Union, Callable
from django.conf import settings
from django.urls import reverse
from collections import defaultdict

import logging
logger = logging.getLogger(__name__)


class Node:
    """A single node in the tree"""

    def __init__(self, parent=None, data=None, relation_data=None):
        # Unique identifier for this node
        self.identifier = id(self)

        self.parent: Node = parent
        # Main data object for this node
        self.data = data
        # Secondary optional data for relation information
        self.relation_data = relation_data

    def __str__(self):
        return str(self.data)


class Tree:
    """Tree data structure composed of nodes"""

    # Characters used for building string representation
    data_start = '- '
    spacing_char = ' '
    end_char = '\n'

    def __init__(self, root: Node):
        self.root: Node = root
        self.nodes: Dict[int, Node] = {}
        self.children: Dict[int, List[int]] = defaultdict(list)

    def add_node(self, node):
        self.nodes[node.identifier] = node
        # Add relationship to parent
        self.children[node.parent.identifier].append(node.identifier)

    def add_bulk_relations(self, start: Node, relations: List[Tuple[int, int, Any]], datadict: Dict[int, Any]):
        """
        Add's relations in bulk from (parent, child) tuples
        To maintain tree structure id's that appear multiple times in tree will have new nodes created
        """
        # Build dict of parent id -> list of tuples containing child id and relation info
        relation_dict: Dict[int, List[Tuple[int, Any]]] = defaultdict(list)
        for rel in relations:
            relation_dict[rel[0]].append(rel[1:])

        # Stack of node, depth tuples
        node_stack = [(start, 1)]

        # While there are elements in the stack
        while node_stack:
            # Pop node off stack
            next_node, depth = node_stack.pop()
            # Depth check
            if depth > settings.CLUSTER_DISPLAY_DEPTH:
                break
            # Add to tree if not root
            if next_node != start:
                self.add_node(next_node)
            # Create child nodes and add to stack
            children = relation_dict.get(next_node.data.id, [])
            for child_id, relation_info in children:
                item = datadict.get(child_id, None)
                if item:
                    node_stack.append(
                        (Node(next_node, item, relation_info), depth + 1)
                    )
                else:
                    logger.error(f'id {child_id} not found in datadict')

    def get_node_children(self, identifier, sort_by=None) -> List[Node]:
        children = [self.nodes[i] for i in self.children[identifier]]
        if callable(sort_by):
            children.sort(key=sort_by)
        return children

    def get_string(self, node, level=0) -> str:
        """Recurively build string representation of tree"""
        s = (self.spacing_char * level) + self.data_start + str(node) + self.end_char
        for sub_node in self.get_node_children(node.identifier):
            s += self.get_string(sub_node, level + 1)
        return s

    def get_nested_list(self, node: Node, getter: Callable[[Node], Any]) -> List[Union[List, Any]]:
        """Get a nested list of some data for each node"""
        nlist = [getter(node)]
        sublist = []

        for sub_node in self.get_node_children(node.identifier):
            sublist.extend(self.get_string_list(sub_node))

        if sublist:
            nlist.append(sublist)

        return nlist

    def get_string_list(self, node) -> List[Union[List, str]]:
        """Get a nested list of string representations of each node"""
        return self.get_nested_list(node, lambda n: str(n))

    def get_values_list(self, node):
        return self.get_nested_list(node, lambda n: n)

    def get_values(self, node, start_depth=0, sort_by=None) -> List[Tuple[Node, int]]:
        vals = [(node, start_depth)]

        for sub_node in self.get_node_children(node.identifier, sort_by=sort_by):
            vals.extend(self.get_values(sub_node, start_depth + 1, sort_by=sort_by))

        return vals

    @property
    def string_list(self):
        return self.get_string_list(self.root)

    @property
    def values(self):
        return self.get_values(self.root)

    def __str__(self):
        return self.get_string(self.root)


class Breadcrumb:
    """Object representing a single breadcrumb"""

    def __init__(self, name: str, url_name='', url_args=[], active=False):
        self._name = name
        self.active = active

        if url_name:
            self.url = reverse(url_name, args=url_args)
        else:
            self.url = ''

    @property
    def name(self):
        """Display name for breadcrumb"""
        return truncate_words(self._name, 10)
