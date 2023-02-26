import threading
from typing import Callable, Dict, List, TypeVar, Type

from chatroom.router.router import ChatroomRouter
from chatroom.router.endpoint import PythonEndpoint
from chatroom.topic import StringTopic, Topic, SetTopic, TopicFactory
from chatroom.logger import Logger, DEBUG
from ..command import ChangeCommand, CommandManager
from chatroom.topic_change import Change, InvalidChangeException, SetChangeTypes
from chatroom.utils import WeakKeyDict

import weakref

class ChatroomServer:
    def __init__(self,port) -> None:
        self._logger = Logger(DEBUG,"Server")
        self._command_manager = CommandManager(on_recording_stop=self._OnRecordingStop)
        self._endpoint = PythonEndpoint(0,self)
        self._router = ChatroomRouter(self._endpoint,port=port)
        self._topics : WeakKeyDict[str,Topic] = WeakKeyDict(on_removed=self._OnTopicGarbageCollected)
        self._services : Dict[str,Callable] = {}
        self._evnts : Dict[str,threading.Event] = {}
    
    '''
    Callbacks
    '''

    def _OnRecordingStop(self,recorded_commands):
        '''
        Called when the command manager finishes recording
        '''
        command_dicts = [command.Serialize() for command in recorded_commands]
        self._endpoint.SendToRouter("update",changes = command_dicts)
        self._command_manager.Commit()

    def _OnTopicGarbageCollected(self,topic_name):
        '''
        Called when a topic is garbage collected
        '''
        self._endpoint.SendToRouter("unsubscribe",topic_name=topic_name)

    '''
    Interface for router
    '''

    def _handle_client_update(self,client_id,changes):
        try:
            for item in changes:
                topic_name, change_dict = item['topic_name'], item['change']
                topic = self._topics[topic_name]
                change = topic.DeserializeChange(change_dict)
                topic.ApplyChangeExternal(change)
                
        except InvalidChangeException as e:
            self._command_manager.Reset()
            self._endpoint.SendToRouter("reject_update",client_id=client_id,topic_name=changes[0]['topic_name'],change=changes[0]['change'],reason=str(e))
            return
        
    def _handle_update(self,changes):
        '''
        This is called soon after the server subscribes to a topic. It is used to update the server's state to the latest state of the topic.
        '''
        try:
            assert len(changes) == 1
            change = changes[0]
            topic_name, change_dict = change['topic_name'], change['change']
            assert change_dict['type'] == 'set'
            topic = self._topics[topic_name]
            change = topic.DeserializeChange(change_dict)
            topic.ApplyChange(change)
            print('Received update')
            self._evnts[topic_name].set()
        except InvalidChangeException as e:
            self._logger.Error(f"Invalid change: {e} when subscribing to topic {topic_name}. This happens when some clients have accessed the topic earlier than the server. Avoid that.")
            return
        
    def _handle_request(self,service_name,args,request_id):
        '''
        Handle a request from a client
        '''
        response = self._services[service_name](**args)
        self._endpoint.SendToRouter("response",response = response,request_id = request_id)

    '''
    Public functions
    '''
    def RegisterService(self,service_name:str,service:Callable):
        '''
        Register a service
        '''
        self._services[service_name] = service
        self._endpoint.SendToRouter("register_service",service_name=service_name)
                                    
    T = TypeVar('T',bound=Topic)
    def RegisterTopic(self,topic_name,type:Type[T],value=None)->T:
        if topic_name in self._topics:
            topic = self._topics[topic_name]
            assert isinstance(topic,type)
            return topic
        else:
            topic = self._topics[topic_name] = type(topic_name,lambda name: self._topics[name],self._command_manager)
            # send to router
            # Server doesn't really subscribe to topics. To "subscribe" means to tell the router that the server is interested in the topic,
            # so do not garbage collect it.
            self._endpoint.SendToRouter("subscribe",topic_name=topic_name,type=type.GetTypeName()) 
            evnt = self._evnts[topic_name] = threading.Event()
            print("Waiting for topic to be updated")
            evnt.wait() # wait for the topic to be updated to the latest state
            self._logger.Debug(f"Added topic {topic_name}")
            return topic
    '''
    Shortcuts
    '''