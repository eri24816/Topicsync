from typing import Dict

from chatroom.client.topic import Topic
from chatroom.router.router import ChatroomRouter
from chatroom.router.endpoint import PythonEndpoint
from .command import ChangeCommand, CommandManager
from chatroom.topic_change import Change, InvalidChangeException

class ChatroomServer:
    def __init__(self) -> None:
        self.command_manager = CommandManager()
        self._router = ChatroomRouter(PythonEndpoint(self))
        self._topics : Dict[str,Topic] = {}

    '''
    Interface for router
    '''

    def _handle_client_update(self,changes):
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
            return False, str(e)


    '''
    Shortcuts
    '''

    def GetTopic(self,topic_name):
        return self._topics[topic_name]
    