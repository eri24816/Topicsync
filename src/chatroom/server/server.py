import asyncio
from typing import Any, Callable, Dict, List, TypeVar

from websockets.server import serve as websockets_serve
from chatroom import state_machine

from chatroom.server.client_manager import ClientManager, Client
from chatroom.service import Service
from chatroom.state_machine import StateMachine, Transition
from chatroom.topic import Topic, SetTopic
from chatroom.logger import Logger, DEBUG
from chatroom.change import Change


class ChatroomServer:
    def __init__(self, port: int, host:str='localhost',on_transition_done=lambda transition:None) -> None:
        self._port = port
        self._host = host
        self._logger = Logger(DEBUG, "Server")
        def get_value(topic_name):
            topic = self._state_machine.get_topic(topic_name)
            return topic.get()
        def exists_topic(topic_name):
            return self._state_machine.has_topic(topic_name)
        self._client_manager = ClientManager(get_value,exists_topic)
        self._services: Dict[str, Service] = {}
        self._state_machine = StateMachine(self._on_changes_made,on_transition_done)

        self._topic_set = self._state_machine.add_topic("_chatroom/topics",SetTopic)
        self._topic_set.append({"topic_name":"_chatroom/topics","topic_type":"set"})
        def on_topic_set_append(item):
            self._state_machine.add_topic_s(item["topic_name"],item["topic_type"])
        def on_topic_set_remove(item):
            self._state_machine.remove_topic(item["topic_name"])
        self._topic_set.on_append += on_topic_set_append
        self._topic_set.on_remove += on_topic_set_remove
        
    async def serve(self):
        '''
        Entry point for the server
        '''
        self._logger.info(f"Starting ws server on port {self._port}")
        self._client_manager.register_message_handler("action",self._handle_action)
        self._client_manager.register_message_handler("request",self._handle_request)
        await asyncio.gather(
            self._client_manager.run(),
            websockets_serve(self._client_manager.handle_client,self._host,self._port),
        )
        
    """
    Callbacks
    """

    def _on_changes_made(self, changes:List[Change],actionID:str):
        self._client_manager.send_update(changes,actionID)

    """
    Interface for clients
    """

    def _handle_action(self, sender:Client, commands: list[dict[str, Any]],action_id:str):
        try:
            with self._state_machine.record(action_source=sender.id,action_id=action_id):
                for command_dict in commands:
                    command = Change.deserialize(command_dict)
                    self._state_machine.apply_change(command)

        except Exception as e:
            sender.send("reject",reason=repr(e))

    def _handle_request(self, sender:Client, service_name, args, request_id):
        """
        Handle a request from a client
        """
        service = self._services[service_name]
        if service.pass_client_id:
            args["sender"] = sender.id
        response = service.callback(**args)
        sender.send("response", response=response, request_id=request_id)

    """
    API
    """

    def register_service(self, service_name: str, callback: Callable, pass_sender=False):
        """
        Register a service

        Args:
            - service_name (str): The name of the service
            - callback (Callable): The callback to call when the service is requested
            - pass_sender (bool, optional): Whether to pass the sender's id to the callback. Defaults to False.
        """
        self._services[service_name] = Service(callback,pass_sender)

    T = TypeVar("T", bound=Topic)
    def get_topic(self, topic_name, type: type[T]) -> T:
        '''
        Get a existing topic
        '''
        if self._state_machine.has_topic(topic_name):
            topic = self._state_machine.get_topic(topic_name)
            if type.get_type_name() == 'generic':
                return topic # type: ignore
            assert isinstance(topic, type)
            return topic
        else:
            raise Exception(f"Topic {topic_name} does not exist")
        
    T = TypeVar("T", bound=Topic)
    def add_topic(self, topic_name, type: type[T]) -> T:
        #TODO: Use dict for topic to imply topic_name check
        if self._state_machine.has_topic(topic_name):
            raise Exception(f"Topic {topic_name} already exists")
        self._topic_set.append({"topic_name":topic_name,"topic_type":type.get_type_name()})
        self._logger.debug(f"Added topic {topic_name}")
        return self.get_topic(topic_name,type)
        
    def remove_topic(self, topic_name):
        if not self._state_machine.has_topic(topic_name):
            raise Exception(f"Topic {topic_name} does not exist")
        topic = self.get_topic(topic_name,Topic)
        topic_type = topic.get_type_name()
        with self._state_machine.record(allow_reentry=True):
            topic.set_to_default()
            self._topic_set.remove({"topic_name":topic_name,"topic_type":topic_type})
        self._logger.debug(f"Removed topic {topic_name}")

    def undo(self,transition:Transition):
        self._state_machine.undo(transition)

    def redo(self,transition:Transition):
        self._state_machine.redo(transition)