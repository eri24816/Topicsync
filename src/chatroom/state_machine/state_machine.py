from __future__ import annotations
from typing import TYPE_CHECKING
from contextlib import contextmanager
from typing import Any, Callable, List
from chatroom.command import ChangeCommand
from chatroom.topic_change import InvalidChangeException
if TYPE_CHECKING:
    from chatroom.topic import Topic
    from chatroom.topic_change import Change

class Transition:
    def __init__(self,commands:List[ChangeCommand],actionSource:int):
        self._commands = commands
        self._actionSource = actionSource

    def Execute(self):
        for command in self._commands:
            command.Execute()

    def Undo(self):
        for command in reversed(self._commands):
            command.Undo()

class StateMachine:
    def __init__(self, on_changes_made:Callable[[List[ChangeCommand]], None]=lambda *args:None, on_transition_done: Callable[[Transition], None]=lambda *args:None):
        self._state : dict[str,Topic] = {}
        self._current_transition : List[ChangeCommand] = []
        self._isRecording = False
        self._changes_made : List[ChangeCommand] = []
        self._on_changes_made = on_changes_made
        self._on_transition_done = on_transition_done
        self._error_has_occured_in_transition = False
        self._recursion_enabled = True
        self._apply_change_call_stack = []
    
    def AddTopic(self,topic:Topic):
        self._state[topic.GetName()] = topic

    def GetTopic(self,topicName:str)->Topic:
        return self._state[topicName]
    
    def HasTopic(self,topicName:str):
        return topicName in self._state
    
    def CreateChangeCommand(self,topic_name:str,change:Change):
        '''
        A change command depends on a GetTopic function, which is in the state machine, so we need to create it here
        '''
        return ChangeCommand(topic_name,change,self.GetTopic)
    
    def DesearializeChangeCommand(self,command_dict:dict[str,Any]):
        '''
        Deserializing version of CreateChangeCommand
        '''
        return ChangeCommand.Deserialize(command_dict,self.GetTopic)

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
            if self._error_has_occured_in_transition:
                print("An error has occured in the transition but was catched by the user code. Cleaning up the failed transition.")
                self._CleanupFailedTransition()
                raise Exception("An error has occured in the transition but was catched by the user code.")
            else:
                newTransition = Transition(self._current_transition,actionSource)
                self._on_transition_done(newTransition)
        finally:
            self._isRecording = False
            self._NotifyChanges()
            self._current_transition = []

    def _CleanupFailedTransition(self):
        try:
            with self._DisableRecursion():
                for command in reversed(self._current_transition):
                    topic,inv_change = self.GetTopic(command.topic_name),command.change.Inverse()
                    old_value,new_value = topic.ApplyChange(inv_change,notify_listeners=False)
                    topic.NotifyListeners(inv_change,old_value,new_value)
                    self._changes_made.remove(command)
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

    def ApplyChange(self,command:ChangeCommand):
        #TODO: stateless topic branch
        if not self._recursion_enabled:
            return
        if not self._isRecording:
            raise Exception("You must change the state in the StateMachine.Record context")
        
        # Prevents infinite recursion
        if command.topic_name in self._apply_change_call_stack:
            return
        
        with self._TrackApplyChange(command.topic_name):
            topic,change = self.GetTopic(command.topic_name),command.change

            try:
                old_value,new_value = topic.ApplyChange(change,notify_listeners=False) # If a exception is raised here, the change is not applied and the command is not added to the _current_transition
            except Exception:
                self._error_has_occured_in_transition = True
                raise

            self._current_transition.append(command)
            self._changes_made.append(command)

            topic.NotifyListeners(command.change,old_value,new_value) # If a exception is raised here,the command is added to the _current_transition. The cleanup process will undo the change.

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


