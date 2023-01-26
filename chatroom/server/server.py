from typing import Dict

from chatroom.router.router import ChatroomRouter
from chatroom.router.endpoint import PythonEndpoint
from ..command import ChangeCommand, CommandManager
from chatroom.topic_change import Change, InvalidChangeException

class ChatroomServer:
    def __init__(self,port) -> None:
        self.command_manager = CommandManager()
        self._endpoint = PythonEndpoint(self)
        self._router = ChatroomRouter(self._endpoint,port=port)
        self._topics : Dict[str,Topic] = {}
        self._topics['/'] = Topic(self,'/')

    '''
    Interface for router
    '''

    def _handle_client_update(self,client,changes):
        try:
            with self.command_manager.Record():
                for item in changes:
                    topic_name = item['topic_name']
                    change = Change.Deserialize(self._topics[topic_name].GetTypeName(),item['change'])
                    command = ChangeCommand(self,topic_name,change)
                    self.command_manager.Add(command)
                    
        except InvalidChangeException as e:
            print(e)
            self.command_manager.Reset()
            self._endpoint.SendToRouter("reject_update",client=client,topic_name=topic_name,change=change,reason=str(e))
            return
        
        change_commands = self.command_manager.Commit()
        for command in change_commands:
            if isinstance(command,ChangeCommand):
                self._endpoint.SendToRouter("update",client=client,topic_name=command.topic_name,change=command.change.Serialize())

    '''
    Shortcuts
    '''

    def GetTopic(self,topic_name):
        return self._topics[topic_name]
    