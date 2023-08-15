'''
The transition tree is used by StateMachine.record() to keep track of the changes in transitions.
'''

from typing import Callable, List
from contextlib import contextmanager

from chatroom.change import Change
from chatroom.topic import Topic
from chatroom.state_machine.changes_tree import ChangesTree, Tag

class Node:
    def __init__(self,parent:'Node|RootNode',change:Change,get_topic:Callable[[str],Topic],changes_list:List[Change],changes_tree:ChangesTree):
        self.is_root = False
        self.parent = parent
        self.change = change
        self.children : List[Node] = []
        self.get_topic = get_topic
        self.changes_list = changes_list
        self.changes_tree = changes_tree # for debugging

    def clear_subtree(self):
        for child in reversed(self.children):
            child.clear_subtree()
        if not self.is_root:
            topic,inv_change = self.get_topic(self.change.topic_name),self.change.inverse()

            with self.changes_tree.add_child_and_move_cursor(inv_change,Tag.INVERSED):
                topic.apply_change(inv_change)

            self.changes_list.append(inv_change)
            self.parent.children.remove(self)


class RootNode(Node):
    def __init__(self):
        self.is_root = True
        self.children : List[Node] = []


class TransitionTree:
    def __init__(self,get_topic:Callable[[str],Topic],changes_list:List[Change],changes_tree:ChangesTree):
        self.root = RootNode()
        self.cursor = self.root
        self.get_topic = get_topic
        self.changes_list = changes_list
        self.changes_tree = changes_tree # for debugging

    def add_child(self,change:Change):
        node = Node(self.cursor,change,self.get_topic,self.changes_list,self.changes_tree)
        self.cursor.children.append(node)
        return node
    
    def clear_subtree(self):
        self.cursor.clear_subtree()
        
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