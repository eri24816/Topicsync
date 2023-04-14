from __future__ import annotations
from typing import TYPE_CHECKING, TypeVar
from contextlib import contextmanager
from typing import Any, Callable, List
from chatroom.topic import Topic, TopicFactory
from chatroom.topic_change import InvalidChangeException
if TYPE_CHECKING:
    from chatroom.topic_change import Change

class Transition:
    def __init__(self,changes:List[Change],actionSource:int):
        self._changes = changes
        self._actionSource = actionSource

class StateMachine:
    def __init__(self, on_changes_made:Callable[[List[Change]], None]=lambda *args:None, on_transition_done: Callable[[Transition], None]=lambda *args:None):
        self._state : dict[str,Topic] = {}
        self._current_transition : List[Change] = []
        self._isRecording = False
        self._changes_made : List[Change] = []
        self._on_changes_made = on_changes_made
        self._on_transition_done = on_transition_done
        self._recursion_enabled = True
        self._apply_change_call_stack = []
    
    T = TypeVar('T', bound=Topic)
    def AddTopic(self,name:str,topic_type:type[T])->T:
        topic = topic_type(name,self)
        self._state[name] = topic
        return topic
    
    def AddTopic_s(self,name:str,topic_type:str)->Topic:
        topic = TopicFactory(name,topic_type,self)
        self._state[name] = topic
        return topic
    
    def RemoveTopic(self,name:str):
        del self._state[name]

    def GetTopic(self,topicName:str)->Topic:
        return self._state[topicName]
    
    def HasTopic(self,topicName:str):
        return topicName in self._state

    @contextmanager
    def _DisableRecursion(self):
        self._recursion_enabled = False
        try:
            yield
        finally:
            self._recursion_enabled = True

    @contextmanager
    def Record(self,actionSource:int = 0):
        self._isRecording = True
        self._error_has_occured_in_transition = False
        self._changes_made = []
        try:
            yield
        except Exception:
            self._isRecording = False
            print("An error has occured in the transition. Cleaning up the failed transition.")
            self._CleanupFailedTransition()
            raise
        else:
            self._isRecording = False
            newTransition = Transition(self._current_transition,actionSource)
            self._on_transition_done(newTransition)
        finally:
            self._isRecording = False
            self._NotifyChanges()
            self._current_transition = []

    def _CleanupFailedTransition(self):
        try:
            with self._DisableRecursion():
                for change in reversed(self._current_transition):
                    topic,inv_change = self.GetTopic(change.topic_name),change.Inverse()
                    old_value,new_value = topic.ApplyChange(inv_change,notify_listeners=False)
                    topic.NotifyListeners(inv_change,old_value,new_value)
                    self._changes_made.remove(change)
        except Exception as e:
            print("An error has occured while trying to undo the failed transition. The state is now in an inconsistent state. The error was: " + str(e))
            raise

    def _NotifyChanges(self):
        self._on_changes_made(self._changes_made)
        self._changes_made = []

    @contextmanager
    def _TrackApplyChange(self,topic_name):
        self._apply_change_call_stack.append(topic_name)
        try:
            yield
        finally:
            self._apply_change_call_stack.pop()

    def ApplyChange(self,change:Change):
        #TODO: stateless topic branch
        if not self._recursion_enabled:
            return
        if not self._isRecording:
            with self.Record():
                self.ApplyChange(change)
            return
        
        # Prevents infinite recursion
        if change.topic_name in self._apply_change_call_stack:
            return
        
        with self._TrackApplyChange(change.topic_name):
            topic = self.GetTopic(change.topic_name)

            self._current_transition.append(change)
            self._changes_made.append(change)
            try:
                topic.ApplyChange(change)
            except:
                # undo the whole subtree
                while self._current_transition[-1] != change:
                    topic = self._current_transition[-1].topic_name
                    change = self._current_transition[-1]
                    self.GetTopic(topic).ApplyChange(change.Inverse(), notify_listeners=False)
                    
                    #! todo: separate _changes_made and _current_transition
                    del self._current_transition[-1]
                    del self._changes_made[-1]

                del self._current_transition[-1]
                del self._changes_made[-1]
                raise

    def Undo(self, transition: Transition):
        raise NotImplementedError
        
        with self._DisableRecursion():
            ...
        self._NotifyChanges()
    
    def Redo(self, transition: Transition):
        raise NotImplementedError
    
        with self._DisableRecursion():
                ...
        self._NotifyChanges()


