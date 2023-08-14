'''
The changes tree is for debugging purpose.
'''

from enum import Enum
from typing import Callable, List
from contextlib import contextmanager

from chatroom.change import Change
from chatroom.topic import Topic

class Tag(Enum):
    NORMAL = 0
    SKIPPED = 1
    NOT_RECORDED = 2

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

    def serialize(self):
        return {
            'name':'',
            'children':[c.serialize() for c in self.children]
        }


class ChangesTree:
    def __init__(self):
        self.root = RootNode()
        self.cursor = self.root

    @contextmanager
    def add_child_under_cursor(self,change:Change,tag:Tag=Tag.NORMAL):
        node = Node(self.cursor,change,tag)
        self.cursor.children.append(node)
        with self.move_cursor(node):
            yield node
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