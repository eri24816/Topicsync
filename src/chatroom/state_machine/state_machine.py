from __future__ import annotations
from typing import TYPE_CHECKING, TypeVar
from contextlib import contextmanager
from typing import Any, Callable, List
from chatroom.topic import Topic, topic_factory
from chatroom.topic_change import InvalidChangeError
if TYPE_CHECKING:
    from chatroom.topic_change import Change

class Transition:
    def __init__(self,changes:List[Change],action_source:int):
        self._changes = changes
        self._action_source = action_source

class StateMachine:
    def __init__(self, on_changes_made:Callable[[List[Change],str], None]=lambda *args:None, on_transition_done: Callable[[Transition], None]=lambda *args:None):
        self._state : dict[str,Topic] = {}
        self._current_transition : List[Change] = []
        self._is_recording = False
        self._changes_made : List[Change] = []
        self._on_changes_made = on_changes_made
        self._on_transition_done = on_transition_done
        self._recursion_enabled = True
        self._apply_change_call_stack = []
    
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
    def _disable_recursion(self):
        self._recursion_enabled = False
        try:
            yield
        finally:
            self._recursion_enabled = True

    @contextmanager
    def record(self,action_source:int = 0,action_id:str = ''):
        self._is_recording = True
        self._error_has_occured_in_transition = False
        self._changes_made = []
        try:
            yield
        except Exception:
            self._is_recording = False
            print("An error has occured in the transition. Cleaning up the failed transition.")
            self._cleanup_failed_transition()
            raise
        else:
            self._is_recording = False
            new_transition = Transition(self._current_transition,action_source)
            self._on_transition_done(new_transition)
        finally:
            self._is_recording = False
            self._on_changes_made(self._changes_made,action_id)
            self._changes_made = []
            self._current_transition = []

    def _cleanup_failed_transition(self):
        try:
            with self._disable_recursion():
                for change in reversed(self._current_transition):
                    topic,inv_change = self.get_topic(change.topic_name),change.inverse()
                    old_value,new_value = topic.apply_change(inv_change,notify_listeners=False)
                    topic.notify_listeners(inv_change,old_value,new_value)
                    self._changes_made.remove(change)
        except Exception as e:
            print("An error has occured while trying to undo the failed transition. The state is now in an inconsistent state. The error was: " + str(e))
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
        if not self._recursion_enabled:
            return
        if not self._is_recording:
            with self.record():
                self.apply_change(change)
            return
        
        # Prevents infinite recursion
        if change.topic_name in self._apply_change_call_stack:
            return
        
        with self._track_apply_change(change.topic_name):
            topic = self.get_topic(change.topic_name)

            self._current_transition.append(change)
            self._changes_made.append(change)
            try:
                topic.apply_change(change)
            except:
                # undo the whole subtree
                while self._current_transition[-1] != change:
                    topic = self._current_transition[-1].topic_name
                    change = self._current_transition[-1]
                    self.get_topic(topic).apply_change(change.inverse(), notify_listeners=False)
                    
                    #! todo: separate _changes_made and _current_transition
                    del self._current_transition[-1]
                    del self._changes_made[-1]

                del self._current_transition[-1]
                del self._changes_made[-1]
                raise

    def undo(self, transition: Transition):
        raise NotImplementedError
        
        with self._disable_recursion():
            ...
        self._NotifyChanges()
    
    def redo(self, transition: Transition):
        raise NotImplementedError
    
        with self._disable_recursion():
                ...
        self._NotifyChanges()


