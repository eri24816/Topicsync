from __future__ import annotations
import contextlib
from typing import Callable, TYPE_CHECKING
from chatroom.topic_change import Change
if TYPE_CHECKING:
    from chatroom.topic import Topic


class Command:
    def __init__(self) -> None:
        pass
    def Execute(self):
        raise NotImplementedError
    def Undo(self):
        raise NotImplementedError
    def Redo(self):
        raise NotImplementedError

class ChangeCommand(Command):
    def __init__(self,get_topic_by_name:Callable[[None],Topic],topic_name,change:Change) -> None:
        super().__init__()
        self.get_topic_by_name = get_topic_by_name
        self.topic_name = topic_name # Note the topic name is stored to avoid reference to a topic object to be deleted.
        self.change = change
    def Execute(self):
        self.get_topic_by_name(self.topic_name).ApplyChange(self.change)
    def Undo(self):
        self.get_topic_by_name(self.topic_name).ApplyChange(self.change.Inverse())
    def Redo(self):
        self.get_topic_by_name(self.topic_name).ApplyChange(self.change)

class CommandManager:
    class RecordContext:
        '''
        A context manager that records the command and add it to the command manager when the context is exited.
        '''
        def __init__(self,command_manager:CommandManager) -> None:
            self._command_manager = command_manager
        def __enter__(self):
            self._command_manager.StartRecording()
        def __exit__(self,exc_type,exc_value,traceback):
            self._command_manager.StopRecording()
        
        
    def __init__(self,on_recording_stop = lambda recorded_commands:None) -> None:
        self.recorded_commands: list[ChangeCommand] = []
        self._is_recording = False
        self._on_recording_stop = on_recording_stop

    def StartRecording(self):
        self._is_recording = True

    def StopRecording(self):
        self._is_recording = False
        self._on_recording_stop(self.recorded_commands)
    
    def Record(self,allow_already_recording=False):
        if self._is_recording:
            if allow_already_recording:
                return contextlib.nullcontext()
            else:
                raise Exception('The command manager is already recording.')
        return CommandManager.RecordContext(self)
    

    def Add(self,command:ChangeCommand):
        command.Execute()
        if self._is_recording:
            self.recorded_commands.append(command)

    def Reset(self):
        for command in reversed(self.recorded_commands):
            command.Undo()
        self.recorded_commands = []

    def Commit(self):
        temp = self.recorded_commands
        self.recorded_commands = []
        return temp
    
