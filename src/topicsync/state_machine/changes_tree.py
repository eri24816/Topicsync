'''
The changes tree is for debugging purpose.
'''

from enum import Enum
from typing import Callable, List
from contextlib import contextmanager

from topicsync.change import Change
from topicsync.topic import Topic

class Tag(Enum):
    AUTO = 0
    SKIPPED = 1
    MANUAL = 2
    ERROR = 3
    INVERSED = 4

class Node:
    def __init__(self,parent:'Node|RootNode',change:Change,tag:Tag):
        self.is_root = False
        self.parent = parent
        self.change = change
        self.children : List[Node] = []
        self.tag = tag

    def serialize(self):
        change_dict = self.change.serialize()
        return {
            'name':f'{self.change.topic_name}\n{change_dict["type"]}',
            'change':str(change_dict),
            'children':[c.serialize() for c in self.children],
            'tag':self.tag.name
        }

class RootNode(Node):
    def __init__(self):
        self.is_root = True
        self.children : List[Node] = []
        self.tag = Tag.AUTO

    def serialize(self):
        return {
            'name':'',
            'children':[c.serialize() for c in self.children],
            'tag':self.tag.name
        }


class ChangesTree:
    def __init__(self):
        self.root = RootNode()
        self.cursor = self.root

    @contextmanager
    def add_child_and_move_cursor(self,change:Change,tag:Tag=Tag.AUTO):
        node = self.add_child(change,tag)
        with self.move_cursor(node):
            yield node

    def add_child(self,change:Change,tag:Tag=Tag.AUTO):
        node = Node(self.cursor,change,tag)
        self.cursor.children.append(node)
        return node
        
    def preorder_traversal(self,root:Node|RootNode):
        if not root.is_root:
            yield root.change
        for child in root.children:
            yield from self.preorder_traversal(child)

    def __str__(self) -> str:
        return str([c.serialize() for c in self.preorder_traversal(self.root)])

    @contextmanager
    def move_cursor(self,node:Node):
        old_node = self.cursor
        self.cursor = node
        try:
            yield
        finally:
            self.cursor = old_node

    def serialize(self):
        return self.root.serialize()