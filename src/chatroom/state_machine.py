from __future__ import annotations
import traceback
from typing import TYPE_CHECKING, TypeVar
from contextlib import contextmanager
from typing import Any, Callable, List
from chatroom.topic import Topic, topic_factory
from chatroom.logger import Logger
if TYPE_CHECKING:
    from chatroom.change import Change

class Transition:
    def __init__(self,changes:List[Change],action_source:int):
        self.changes = changes
        self.action_source = action_source

class StateMachine:
    def __init__(self, on_changes_made:Callable[[List[Change],str], None]=lambda *args:None, on_transition_done: Callable[[Transition], None]=lambda *args:None):
        self._state : dict[str,Topic] = {}
        self._current_transition : List[Change] = []
        self._is_recording = False
        self._changes_made : List[Change] = []
        self._on_changes_made = on_changes_made
        self._on_transition_done = on_transition_done
        self._max_recursive_depth = 1e4
        self._apply_change_call_stack = []
        self._logger = Logger(0,"State")
    
    T = TypeVar('T', bound=Topic)
    def add_topic(self,name:str,topic_type:type[T])->T:
        topic = topic_type(name,self)
        self._state[name] = topic
        return topic
    
    def add_topic_s(self,name:str,topic_type:str)->Topic:
        topic = topic_factory(name,topic_type,self)
        self._state[name] = topic
        return topic
    
    def remove_topic(self,name:str):
        del self._state[name]

    def get_topic(self,topic_name:str)->Topic:
        return self._state[topic_name]
    
    def has_topic(self,topic_name:str):
        return topic_name in self._state

    @contextmanager
    def _limit_recursion(self,max_depth:int = 0):
        self._max_recursive_depth = max_depth
        try:
            yield
        finally:
            self._max_recursive_depth = 1e4

    @contextmanager
    def record(self,action_source:int = 0,action_id:str = '',allow_reentry:bool = False,emit_transition:bool = True):
        #TODO: thread lock
        if self._is_recording and not allow_reentry:
            raise RuntimeError("Cannot call record while already recording")
        self._is_recording = True
        self._error_has_occured_in_transition = False
        self._changes_made = []
        try:
            yield
        except Exception:
            self._is_recording = False
            self._logger.warning("An error has occured in the transition. Cleaning up the failed transition. The error was: " + str(traceback.format_exc()))
            self._cleanup_failed_transition()
            raise
        else:
            self._is_recording = False
            if emit_transition:
                new_transition = Transition(self._current_transition,action_source)
                self._on_transition_done(new_transition)
        finally:
            self._is_recording = False
            self._on_changes_made(self._changes_made,action_id)
            self._changes_made = []
            self._current_transition = []

    def _cleanup_failed_transition(self):
        try:
            with self._limit_recursion():
                for change in reversed(self._current_transition):
                    topic,inv_change = self.get_topic(change.topic_name),change.inverse()
                    topic.apply_change(inv_change)
                    self._changes_made.remove(change)
        except Exception as e:
            self._logger.error("An error has occured while trying to undo the failed transition. The state is now in an inconsistent state. The error was: " + str(e))
            raise

    @contextmanager
    def _track_apply_change(self,topic_name):
        self._apply_change_call_stack.append(topic_name)
        try:
            yield
        finally:
            self._apply_change_call_stack.pop()

    def apply_change(self,change:Change):
        #TODO: stateless topic branch
        if len(self._apply_change_call_stack)+1 > self._max_recursive_depth:
            return
        if not self._is_recording:
            with self.record():
                self.apply_change(change)
            return
        
        # Prevent infinite recursion
        
        if change.topic_name in self._apply_change_call_stack:
            return
        
        # Apply the change
        
        self._current_transition.append(change)
        self._changes_made.append(change)
        topic = self.get_topic(change.topic_name)

        try:
            with self._track_apply_change(change.topic_name):
                topic.apply_change(change)
        except:
            # Undo the subtree which was applied in consequence of this change
            self._undo_subtree(self._current_transition,change)
            raise

    def _undo_subtree(self,transition:List[Change],root_of_subtree:Change):
        with self._limit_recursion():
            while (change := transition.pop()) != root_of_subtree:
                topic,inv_change = self.get_topic(change.topic_name),change.inverse()
                topic.apply_change(inv_change)
                self._changes_made.remove(change)
        
        self._changes_made.remove(root_of_subtree)

    def undo(self, transition: Transition, action_source=0):
        # Record the changes made by the undo
        # Undo should not be recorded as a transition
        with self.record(action_source=action_source,emit_transition=False):
            # Block recursive calls to change stateful topics. Only to undo the transition
            with self._limit_recursion(1):
                # Revert the transition
                for change in reversed(transition.changes):
                    self._logger.debug("Undoing by change: " +str(change.inverse().serialize()))
                    self._logger.debug("Before: " + str(self.get_topic(change.topic_name).get()))
                    self.apply_change(change.inverse())
                    self._logger.debug("After: " + str(self.get_topic(change.topic_name).get()))
    
    def redo(self, transition: Transition):
        # Record the changes made by the undo
        # Redo should not be recorded as a transition
        with self.record(emit_transition=False):
            # Block recursive calls to change stateful topics. Only to undo the transition
            with self._limit_recursion(1):
                # Revert the transition
                for change in transition.changes:
                    self._logger.debug("Redoing change: " +str(change.serialize()))
                    self._logger.debug("Before: " + str(self.get_topic(change.topic_name).get()))
                    self.apply_change(change)
                    self._logger.debug("After: " + str(self.get_topic(change.topic_name).get()))

