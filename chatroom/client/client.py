import queue
import uuid
from typing import TYPE_CHECKING, Callable, Dict, List, Tuple, Type, TypeVar
import websockets
import asyncio
import json
from collections import defaultdict
from chatroom import logger
import threading

from chatroom.topic import StringTopic, Topic, UListTopic, TopicFactory
from chatroom.client.request import Request
from chatroom.utils import MakeMessage, ParseMessage
from chatroom.command import ChangeCommand, CommandManager

# to stop pylance complaning
from websockets.client import connect as ws_connect

class ChatroomClient:
    def __init__(self,host="localhost",port=8765,start=True,log_prefix="client"):
        self._host = f'ws://{host}:{port}'
        self._topics:Dict[str,Topic] = {}
        self._command_manager = CommandManager(on_recording_stop=self._OnRecordingStop)
        self._preview_path : List[ChangeCommand] = []
        self._client_id = None
        self._logger = logger.Logger(logger.DEBUG,prefix=log_prefix)
        self.request_pool:Dict[str,Request] = {}
        self.service_pool:Dict[str,Callable] = {}

        self._message_handlers:Dict[str,Callable] = {}
        for message_type in ['hello','update','request','response','reject_update']:
            self._message_handlers[message_type] = getattr(self,'_handle_'+message_type)
        
        self._root_topic = None

        if start:
            self.Start()


    def __del__(self):
        print("Client deleted")
        self.Stop()

    def _InitializeTopics(self):
        '''
        Initialize the root topic
        '''
        self._root_topic = self._AddTopicAndTrackChildren('','string')

    def _ThreadedStart(self):
        '''
        Run the client in a new thread
        '''
        self._event_loop = asyncio.new_event_loop()
        self._event_loop.run_until_complete(self._Connect())
        self.connected_event.set()
        self._sending_queue = asyncio.Queue(loop=self._event_loop)
        self._event_loop.run_until_complete(self._Run())
        self._event_loop.run_forever()
        
    async def _Run(self):
        '''
        Run send and receive loops
        '''
        self._logger.Info("Chatroom client started")
        self._InitializeTopics()
        await asyncio.gather(self._ReceivingLoop(),self._SendingLoop(),loop=self._event_loop)

    async def _Connect(self):
        '''
        Connect to the server and start the client loop
        '''
        self._ws = await ws_connect(self._host)

    async def _ReceivingLoop(self):
        '''
        Receiving loop
        '''
        try:
            async for message in self._ws:
                self._logger.Debug(f"> {message}")  
                message_type,args = ParseMessage(message)
                if message_type in self._message_handlers:
                    self._message_handlers[message_type](**args)
                else:
                    self._logger.Warning(f"Unknown message type {message_type}")
        except websockets.exceptions.ConnectionClosed:
            self._logger.Info("Connection closed")

    async def _SendingLoop(self):
        '''
        Sending loop
        '''
        try:
            while True:
                message = await self._sending_queue.get()
                await self._ws.send(message)
                self._logger.Debug(f"< {message}")
        except websockets.exceptions.ConnectionClosed:
            self._logger.Info("Connection closed")

    def _SendToServerRaw(self,message):
        '''
        Send a raw string to the server
        '''
        self._event_loop.call_soon_threadsafe(self._sending_queue.put_nowait,message)

    def _SendToRouter(self,*args,**kwargs):
        '''
        Send a message to the server
        '''
        message = MakeMessage(*args,**kwargs)
        self._SendToServerRaw(message)

    '''
    ================================
    Callbacks
    ================================
    '''

    def _OnRecordingStop(self,recorded_commands):
        '''
        Called when the command manager finishes recording
        '''
        command_dicts = [command.Serialize() for command in recorded_commands]
        self._SendToRouter('client_update',changes = command_dicts)
        self._command_manager.Commit()
        self._preview_path += recorded_commands

    def _OnRegisterChild(self,parent_topic,base_name,type):
        '''
        Called when a child topic is registered
        '''
        if f'{parent_topic._name}/{base_name}' in self._topics: # already subscribed
            return self._topics[f'{parent_topic._name}/{base_name}']

        try:
            children_list = self._topics[f'/_cr/children/{parent_topic._name}']
        except KeyError:
            raise ValueError(f'You can\'t create a child of topic {parent_topic._name}')
        assert isinstance(children_list,UListTopic)

        if {'name':base_name,'type':type} not in children_list.GetValue(): # not exist
            children_list.Append({'name':base_name,'type':type})

        return self._AddTopicAndTrackChildren(f'{parent_topic._name}/{base_name}',type)

    '''
    ================================
    Internal API functions
    ================================
    '''

    def _handle_hello(self,id):
        '''
        Handle a hello message from the server
        '''
        self._client_id = id
        self._logger.Info(f"Connected to server as client {self._client_id}")

    def _handle_request(self,service_name,args,request_id):
        '''
        Handle a request from another client
        '''
        response = self.service_pool[service_name](**args)
        self._SendToRouter("response",response = response,request_id = request_id)

    def _handle_response(self,request_id,response):
        '''
        Handle a response from another client
        '''
        request = self.request_pool.pop(request_id)
        request.on_response(response)

    def _handle_update(self,changes):
        '''
        Handle an update message from the server
        '''
        for item in changes:
            topic_name, change_dict = item['topic_name'], item['change']
            topic = self._topics[topic_name]
            change = topic.DeserializeChange(change_dict)

            if len(self._preview_path)>0 and change.id == self._preview_path[0].change.id:
                self._preview_path.pop(0)
            else:
                self.UndoAll(self._preview_path)
                self._preview_path = []
                topic.ApplyChange(change)

    def _handle_reject_update(self,topic_name,change,reason):
        '''
        Handle a rejected update from the server
        '''
        self._logger.Warning(f"Update rejected for topic {topic_name}: {reason}")
        if len(self._preview_path)>0 and change.id == self._preview_path[0].change.id:
            self.UndoAll(self._preview_path)
            self._preview_path = []

    '''
    ================================
    Topic functions
    ================================
    '''
    def _AddTopic(self,name,type):
        topic = self._topics[name] = TopicFactory(name,type,self._OnRegisterChild,lambda name: self._topics[name],self._command_manager)
        self._SendToRouter('subscribe',topic_name=name)
        self._logger.Debug(f"Added topic {name} of type {type}")
        return topic
    
    def _AddTopicAndTrackChildren(self,name,type):
        self._AddTopic(name,type)
        children_list = self._AddTopic(f'/_cr/children/{name}','u_list')
        assert isinstance(children_list,UListTopic)
        children_list.on_append += lambda data: self._OnChildrenListAppend(name,data)
        children_list.on_remove += lambda data: self._OnChildrenListRemove(name,data)
        
        return self._topics[name]

    def _OnChildrenListAppend(self,parent_name,data):
        pass # Do nothing because the added topic will be created in _OnRegisterChild.

    def _RemoveTopic(self,name):
        del self._topics[name]
        self._SendToRouter('unsubscribe',topic_name=name)
        self._logger.Debug(f"Removed topic {name}")

    def _RemoveTopicAndUntrackChildren(self,name):
        self._RemoveTopic(name)
        self._RemoveTopic(f'/_cr/children/{name}')

    def _OnChildrenListRemove(self,parent_name,data):
        name = data['name']
        self._RemoveTopicAndUntrackChildren(f'{parent_name}/{name}')

    '''
    ================================
    Public functions
    ================================
    '''

    def Start(self):
        '''
        Run the client
        '''
        self.connected_event =threading.Event()
        self.thread = threading.Thread(target=self._ThreadedStart)
        self.thread.daemon = True
        self.thread.start()
        self.connected_event.wait()
    
    def Stop(self):
        '''
        Disconnect from the server
        '''
        asyncio.run(self._ws.close())
        self.thread.join()
    
    def DeleteTopic(self,topic_name):
        '''
        Delete a topic
        '''
        self._SendToRouter("delete_topic",topic_name=topic_name)

    def MakeRequest(self,service_name:str,args:Dict,on_response:Callable):
        '''
        Request a service from another client. Does not wait for the response.
        '''
        id = str(uuid.uuid4())
        request = Request(id,on_response)
        self.request_pool[id] = request
        self._SendToRouter("request",service_name=service_name,args=args,request_id=id)
        return request

    def RegisterService(self,service_name:str,service:Callable):
        '''
        Register a service
        '''
        self.service_pool[service_name] = service
        self._SendToRouter("register_service",service_name=service_name)

    def GetRootTopic(self):
        '''
        Get the root topic
        '''
        return self._topics['']

    '''
    Shortcut functions
    '''
    def UndoAll(self,commands:List[ChangeCommand]):
        '''
        Undo all changes
        '''
        for command in reversed(commands):
            command.Undo()