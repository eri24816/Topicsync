from __future__ import annotations
from chatroom.topic_change import Change

class Command:
    def __init__(self,server) -> None:
        pass
    def Execute(self):
        raise NotImplementedError
    def Undo(self):
        raise NotImplementedError
    def Redo(self):
        raise NotImplementedError

class ChangeCommand(Command):
    def __init__(self,server,topic_name,change:Change) -> None:
        super().__init__(server)
        self.server = server
        self.topic_name = topic_name # Note the topic name is stored to avoid reference to a topic object to be deleted.
        self.change = change
    def Execute(self):
        self.server.GetTopic(self.topic_name).ApplyChange(self.change)
    def Undo(self):
        self.server.GetTopic(self.topic_name).ApplyChange(self.change.Inverse())
    def Redo(self):
        self.server.GetTopic(self.topic_name).ApplyChange(self.change)

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
        
        
    def __init__(self) -> None:
        self._recorded_commands = []
        self._recording = False

    def StartRecording(self):
        self._recording = True

    def StopRecording(self):
        self._recording = False
    
    def Record(self):
        return CommandManager.RecordContext(self)

    def Add(self,command:Command):
        command.Execute()
        if self._recording:
            self._recorded_commands.append(command)

    def Reset(self):
        for command in reversed(self._recorded_commands):
            command.Undo()
        self._recorded_commands = []

    def Commit(self):
        temp = self._recorded_commands
        self._recorded_commands = []
        return temp
    
