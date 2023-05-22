import asyncio
from typing import Any, Callable, Dict, List, TypeVar

from websockets.server import serve as websockets_serve
from chatroom import state_machine

from chatroom.server.client_manager import ClientManager, Client
from chatroom.service import Service
from chatroom.state_machine import StateMachine, Transition
from chatroom.topic import DictTopic, EventTopic, Topic, SetTopic
from chatroom.logger import Logger, DEBUG
from chatroom.change import Change


class ChatroomServer:
    def __init__(self, port: int, host:str='localhost',on_transition_done=lambda transition:None) -> None:
        self._port = port
        self._host = host
        self._logger = Logger("Server")
        def get_value(topic_name):
            topic = self._state_machine.get_topic(topic_name)
            return topic.get()
        def exists_topic(topic_name):
            return self._state_machine.has_topic(topic_name)
        self._client_manager = ClientManager(get_value,exists_topic)
        self._services: Dict[str, Service] = {}
        self._state_machine = StateMachine(self._on_changes_made,on_transition_done)

        self._topic_list = self._state_machine.add_topic("_chatroom/topic_list",DictTopic,is_stateful=True,init_value=
                                                         {'_chatroom/topic_list':{"type":"dict","is_stateful":True,"boundary_value":{}}}
                                                         )
        self._topic_list.on_add += self._add_topic_raw
        self._topic_list.on_remove += self._remove_topic_raw

        self.record = self._state_machine.record

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

    def _add_topic_raw(self,topic_name,props):
        self._state_machine.add_topic_s(topic_name,props["type"],props["is_stateful"],props["boundary_value"])

    def _remove_topic_raw(self,topic_name):
        self._state_machine.remove_topic(topic_name)

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

    def on(self, event_name: str, callback: Callable, inverse_callback: Callable|None = None, is_stateful: bool = True):
        """
        Register a callback for a event.
        The event can be triggered by the client or the server.

        Args:
            - event_name (str): The name of the event
            - callback (Callable): The callback to call when the event is triggered
        """
        if is_stateful and inverse_callback is None:
            raise ValueError("inverse_callback must be provided if is_stateful is True")
        if not self._state_machine.has_topic(event_name):
            self._state_machine.add_topic(event_name,EventTopic,is_stateful=is_stateful)
        topic = self._state_machine.get_topic(event_name)
        assert isinstance(topic, EventTopic)
        topic.on_emit += callback
        if is_stateful:
            assert inverse_callback is not None
            topic.on_reverse += inverse_callback

    def emit(self, event_name: str, **args):
        """
        Emit a event

        Args:
            - event_name (str): The name of the event
            - args: The arguments to pass to the event callback
        """
        if not self._state_machine.has_topic(event_name):
            self._state_machine.add_topic(event_name,EventTopic)
        topic = self._state_machine.get_topic(event_name)
        assert isinstance(topic, EventTopic)
        topic.emit(args)

    T = TypeVar("T", bound=Topic)
    def topic(self, topic_name, type: type[T]=Topic) -> T:
        '''
        Get a existing topic
        '''
        if self._state_machine.has_topic(topic_name):
            topic = self._state_machine.get_topic(topic_name)
            if type.get_type_name() == 'generic':
                return topic # type: ignore
            #assert isinstance(topic, type)
            assert type is Topic or topic.get_type_name() == type.get_type_name(), f"Topic {topic_name} is of type {topic.get_type_name()} but {type.get_type_name()} was requested"
            return topic # type: ignore
        else:
            raise Exception(f"Topic {topic_name} does not exist")
        
    T = TypeVar("T", bound=Topic)
    def add_topic(self, topic_name, type: type[T],init_value=None) -> T:
        if self._state_machine.has_topic(topic_name):
            raise Exception(f"Topic {topic_name} already exists")
        self._topic_list.add(topic_name,{'type':type.get_type_name(),'boundary_value':init_value,'is_stateful':True})
        self._logger.debug(f"Added topic {topic_name}")
        new_topic = self.topic(topic_name,type)
        return new_topic
        
    def remove_topic(self, topic_name):
        if not self._state_machine.has_topic(topic_name):
            raise Exception(f"Topic {topic_name} does not exist")
        topic = self.topic(topic_name,Topic)
        with self._state_machine.record(allow_reentry=True):
            temp = self._topic_list[topic_name]
            temp['boundary_value'] = topic.get()
            self._topic_list.change_value(topic_name,temp)
            self._topic_list.remove(topic_name)
        self._logger.debug(f"Removed topic {topic_name}")

    def undo(self,transition:Transition):
        self._state_machine.undo(transition)

    def redo(self,transition:Transition):
        self._state_machine.redo(transition)