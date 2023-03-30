import asyncio
from typing import Any, Callable, Dict, List, TypeVar

from websockets.server import serve as websockets_serve

from chatroom.server.client_manager import ClientManager, Client
from chatroom.state_machine.state_machine import StateMachine, Transition
from chatroom.topic import Topic, SetTopic
from chatroom.logger import Logger, DEBUG
from chatroom.utils import astype
from chatroom.command import ChangeCommand
from chatroom.topic_change import InvalidChangeException


class ChatroomServer:
    def __init__(self, port: int, command_handler:Callable[[Any],None], host:str='localhost') -> None:
        self.port = port
        self.host = host
        self._command_handler = command_handler
        self._logger = Logger(DEBUG, "Server")
        self._client_manager = ClientManager()
        self._services: Dict[str, Callable[..., Any]] = {}
        self._state_machine = StateMachine(self._OnChangesMade,self._OnTransitionDone)

    async def Serve(self):
        '''
        Entry point for the server
        '''
        self._logger.Info(f"Starting ws server on port {self.port}")
        self._client_manager.RegisterMessageHandler("action",self._HandleAction)
        self._client_manager.RegisterMessageHandler("request",self._HandleRequest)
        await asyncio.gather(
            self._client_manager.Run(),
            websockets_serve(self._client_manager.HandleClient,self.host,self.port),
        )
        
    """
    Callbacks
    """

    def _OnTransitionDone(self, transition: Transition):
        """
        Called when the state machine finishes a transition
        """

    def _OnChangesMade(self, changes:List[ChangeCommand]):
        self._client_manager.SendUpdate(changes)

    """
    Interface for router
    """

    def _HandleAction(self, sender:Client, action_id: str, commands: list[dict[str, Any]]):
        try:
            with self._state_machine.Record(actionSource=sender.id):
                for command_dict in commands:
                    self._ExecuteClientCommand(command_dict)

        except Exception as e:
            sender.Send("reject_action",action_id=action_id,reason=str(e))
            if not isinstance(e,InvalidChangeException):
                raise
        else:
            sender.Send("accept_action",action_id=action_id)
        
    def _ExecuteClientCommand(self, command_type_and_dict: dict[str, Any]):
        command_type, command_dict = command_type_and_dict["type"], command_type_and_dict["command"]
        if command_type == "change":
            command = ChangeCommand.Deserialize(command_dict, self._state_machine.GetTopic)
            self._state_machine.ApplyChange(command)
        else:
            # Let the app handle the command
            self._command_handler(command_dict)

    def _HandleRequest(self, sender:Client, service_name, args, request_id):
        """
        Handle a request from a client
        """
        response = self._services[service_name](**args)
        sender.Send("response", response=response, request_id=request_id)

    """
    API
    """

    def RegisterService(self, service_name: str, service: Callable):
        """
        Register a service
        """
        self._services[service_name] = service

    T = TypeVar("T", bound=Topic)
    def Topic(self, topic_name, type: type[T]) -> T:
        '''
        Get a topic, or create it if it doesn't exist
        '''
        if self._state_machine.HasTopic(topic_name):
            topic = self._state_machine.GetTopic(topic_name)
            assert isinstance(topic, type)
            return topic
        else:
            topic =  type(topic_name, self._state_machine)
            self._state_machine.AddTopic(topic)
            self._logger.Debug(f"Added topic {topic_name}")
            return topic