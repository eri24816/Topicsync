from contextlib import contextmanager
from typing import Callable, List
from chatroom.topic import Topic
from chatroom.topic_change import InvalidChangeException
from chatroom.command import ChangeCommand

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
    def __init__(self, onTransitionDone: Callable[[Transition], None]):
        self._state : dict[str,Topic] = {}
        self._currentTransition : List[ChangeCommand] = []
        self._isRecording = False
        self._onTransitionDone = onTransitionDone

    @contextmanager
    def RecordTransition(self,actionSource:int = 0):
        self._isRecording = True
        try:
            yield
        except InvalidChangeException as e:
            for command in self._currentTransition:
                command.Undo()
            raise e
        else:
            newTransition = Transition(self._currentTransition,actionSource)
            self._onTransitionDone(newTransition)
        finally:
            self._isRecording = False
            self._currentTransition = []
    
    def ApplyChange(self,command:ChangeCommand):
        command.Execute()
        if self._isRecording:
            self._currentTransition.append(command)

    def GetTopic(self,topicName:str):
        return self._state[topicName]

