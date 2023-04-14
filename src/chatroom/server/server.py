import asyncio
from typing import Any, Callable, Dict, List, TypeVar

from websockets.server import serve as websockets_serve

from chatroom.server.client_manager import ClientManager, Client
from chatroom.state_machine.state_machine import StateMachine, Transition
from chatroom.topic import Topic, SetTopic
from chatroom.logger import Logger, DEBUG
from chatroom.utils import astype
from chatroom.topic_change import Change, InvalidChangeException


class ChatroomServer:
    def __init__(self, port: int, command_handler:Callable[[Any],None], host:str='localhost') -> None:
        self.port = port
        self.host = host
        self._command_handler = command_handler
        self._logger = Logger(DEBUG, "Server")
        def GetValue(topic_name):
            topic = self._state_machine.GetTopic(topic_name)
            return topic.GetValue()
        self._client_manager = ClientManager(GetValue)
        self._services: Dict[str, Callable[..., Any]] = {}
        self._state_machine = StateMachine(self._OnChangesMade,self._OnTransitionDone)

        self.topicSet = self._state_machine.AddTopic("_chatroom/topics",SetTopic)
        self.topicSet.Append({"topic_name":"_chatroom/topics","topic_type":"set"})
        def onTopicSetAppend(item):
            self._state_machine.AddTopic_s(item["topic_name"],item["topic_type"])
        def onTopicSetRemove(item):
            self._state_machine.RemoveTopic(item["topic_name"])
        self.topicSet.on_append += onTopicSetAppend
        self.topicSet.on_remove += onTopicSetRemove
        print(self.topicSet.GetValue())

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

    def _OnChangesMade(self, changes:List[Change],actionID:str):
        self._client_manager.SendUpdate(changes,actionID)

    """
    Interface for router
    """

    def _HandleAction(self, sender:Client, commands: list[dict[str, Any]],action_id:str):
        try:
            with self._state_machine.Record(actionSource=sender.id,actionID=action_id):
                for command_dict in commands:
                    command = Change.Deserialize(command_dict)
                    self._state_machine.ApplyChange(command)

        except Exception as e:
            sender.Send("reject",reason=repr(e))
            # if not isinstance(e,InvalidChangeException):
            #     raise

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
    def getTopic(self, topic_name, type: type[T]) -> T:
        '''
        Get a topic, or create it if it doesn't exist
        '''
        if self._state_machine.HasTopic(topic_name):
            topic = self._state_machine.GetTopic(topic_name)
            assert isinstance(topic, type)
            return topic
        else:
            raise Exception(f"Topic {topic_name} does not exist")
        
    T = TypeVar("T", bound=Topic)
    def AddTopic(self, topic_name, type: type[T]) -> T:
        self.topicSet.Append({"topic_name":topic_name,"topic_type":type.GetTypeName()})
        self._logger.Debug(f"Added topic {topic_name}")
        return self.getTopic(topic_name,type)
        
