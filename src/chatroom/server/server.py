import threading
from typing import Any, Callable, Dict, TypeVar, Type

from chatroom.router.router import ChatroomRouter
from chatroom.router.endpoint import PythonEndpoint
from chatroom.state_machine.state_machine import StateMachine, Transition
from chatroom.topic import Topic, SetTopic
from chatroom.logger import Logger, DEBUG
from ..command import ChangeCommand, CommandManager
from chatroom.topic_change import InvalidChangeException


class ChatroomServer:
    def __init__(self, port: int, command_handler:Callable[[Any],None]) -> None:
        self._logger = Logger(DEBUG, "Server")
        self._command_manager = CommandManager(on_recording_stop=self._OnRecordingStop)
        self._endpoint = PythonEndpoint(0, self)
        self._router = ChatroomRouter(self._endpoint, port=port)
        self._state_machine = StateMachine(self._OnTransitionDone)
        self._services: Dict[str, Callable[..., Any]] = {}
        self._evnts: Dict[str, threading.Event] = {}
        self._command_handler = command_handler

        # temp_ref_keeper = self._topics['_chatroom/topic_list'] = SetTopic('_chatroom/topic_list',lambda name: self._topics[name],self._command_manager)
        self._topic_list = self.RegisterTopic("_chatroom/topic_list", SetTopic)

    """
    Callbacks
    """

    def _OnRecordingStop(self, recorded_commands):
        """
        Called when the command manager finishes recording
        """
        command_dicts = [command.Serialize() for command in recorded_commands]
        self._endpoint.SendToRouter("update", changes=command_dicts)
        self._command_manager.Commit()

    def _OnTransitionDone(self, transition: Transition):
        """
        Called when the state machine finishes a transition
        """

    """
    Interface for router
    """

    def _handle_action(self, client_id: int, action_id: str, commands: list[dict[str, Any]]):
        try:
            with self._state_machine.RecordTransition(actionSource=client_id):
                for command_dict in commands:
                    self._ExecuteClientCommand(command_dict)

        except InvalidChangeException as e:
            self._endpoint.SendToRouter("reject_action",client_id=client_id,action_id=action_id,reason=str(e))
            return
        
    def _ExecuteClientCommand(self, command_type_and_dict: dict[str, Any]):
        command_type, command_dict = command_type_and_dict["type"], command_type_and_dict["command"]
        if command_type == "change":
            command = ChangeCommand.Deserialize(command_dict, self._state_machine.GetTopic)
            self._state_machine.ApplyChange(command)
        else:
            # Let the app handle the command
            self._command_handler(command_dict)

    def _handle_update(self, changes):
        """
        This is called soon after the server subscribes to a topic. It is used to update the server's state to the latest state of the topic.
        """
        try:
            assert len(changes) == 1
            change = changes[0]
            topic_name, change_dict = change["topic_name"], change["change"]
            assert change_dict["type"] == "set"
            topic = self._topics[topic_name]
            change = topic.DeserializeChange(change_dict)
            topic.ApplyChange(change)
            print("Received update")
            self._evnts[topic_name].set()
        except InvalidChangeException as e:
            self._logger.Error(
                f"Invalid change: {e} when subscribing to topic {topic_name}. This happens when some clients have accessed the topic earlier than the server. Avoid that."
            )
            return

    def _handle_topic_created(self, topic_name, type):
        self._topic_list.Append({"topic_name": topic_name, "type": type})

    def _handle_topic_deleted(self, topic_name, type):
        self._topic_list.Remove({"topic_name": topic_name, "type": type})

    def _handle_request(self, service_name, args, request_id):
        """
        Handle a request from a client
        """
        response = self._services[service_name](**args)
        self._endpoint.SendToRouter(
            "response", response=response, request_id=request_id
        )

    """
    Public functions
    """

    def RegisterService(self, service_name: str, service: Callable):
        """
        Register a service
        """
        self._services[service_name] = service
        self._endpoint.SendToRouter("register_service", service_name=service_name)

    T = TypeVar("T", bound=Topic)

    def RegisterTopic(self, topic_name, type: Type[T]) -> T:
        if topic_name in self._topics:
            topic = self._topics[topic_name]
            assert isinstance(topic, type)
            return topic
        else:
            topic = self._topics[topic_name] = type(
                topic_name, lambda name: self._topics[name], self._command_manager
            )
            if topic_name == "_chatroom/topic_list":
                self._topic_list = topic
            # send to router
            # Server doesn't really subscribe to topics. To "subscribe" means to tell the router that the server is interested in the topic,
            # so do not garbage collect it.
            self._endpoint.SendToRouter(
                "subscribe", topic_name=topic_name, type=type.GetTypeName()
            )
            evnt = self._evnts[topic_name] = threading.Event()
            evnt.wait(2)  # wait for the topic to be updated to the latest state
            self._logger.Debug(f"Added topic {topic_name}")
            return topic

    """
    Shortcuts
    """
