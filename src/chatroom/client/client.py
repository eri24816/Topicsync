import queue
import uuid
from typing import TYPE_CHECKING, Callable, Dict, List, Tuple, Type, TypeVar
import websockets
import asyncio
import json
from collections import defaultdict
from chatroom import logger
import threading

from chatroom.topic import StringTopic, Topic, SetTopic, TopicFactory
from chatroom.client.request import Request
from chatroom.topic_change import SetChangeTypes
from chatroom.utils import MakeMessage, ParseMessage, WeakKeyDict
from chatroom.command import ChangeCommand, CommandManager

# to stop pylance complaning
from websockets.client import connect as ws_connect

class ChatroomClient:
    def __init__(self,host="localhost",port=8765,start=True,log_prefix="client"):
        self._host = f'ws://{host}:{port}'
        self._topics : WeakKeyDict[str,Topic] = WeakKeyDict(on_removed=self._OnTopicGarbageCollected)
        self._command_manager = CommandManager(on_recording_stop=self._OnRecordingStop,on_add=self._OnAddCommand)
        self._preview_path : List[ChangeCommand] = []
        self._client_id = None
        self._logger = logger.Logger(logger.DEBUG,prefix=log_prefix)
        self.request_pool:Dict[str,Request] = {}
        self.service_pool:Dict[str,Callable] = {}

        self._message_handlers:Dict[str,Callable] = {}
        for message_type in ['hello','update','request','response','reject_update']:
            self._message_handlers[message_type] = getattr(self,'_handle_'+message_type)
        

        if start:
            self.Start()


    def __del__(self):
        print("Client deleted")
        self.Stop()

    def _ThreadedStart(self):
        '''
        Run the client in a new thread
        '''
        self._event_loop = asyncio.new_event_loop()
        self._event_loop.run_until_complete(self._Connect())
        self._sending_queue = asyncio.Queue(loop=self._event_loop)
        self.connected_event.set()
        self._event_loop.run_until_complete(self._Run())
        self._event_loop.run_forever()
        
    async def _Run(self):
        '''
        Run send and receive loops
        '''
        self._logger.Info("Chatroom client started")
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
        for command in recorded_commands:
            print(command.change.Serialize())
        for command in recorded_commands:
            if isinstance(command.change,SetChangeTypes.SetChange):
                if command.change.value == [5]:
                    raise Exception("ageraegr")
        command_dicts = [command.Serialize() for command in recorded_commands]
        self._SendToRouter('client_update',changes = command_dicts)
        self._command_manager.Commit()

    def _OnAddCommand(self,added_command:ChangeCommand):
        '''
        Called when the command manager adds a command
        '''
        if added_command.preview:
            added_command.Execute()
            self._preview_path.append(added_command)

    def _OnTopicGarbageCollected(self,topic_name):
        '''
        Called when a topic is garbage collected
        '''
        self._SendToRouter('unsubscribe',topic_name=topic_name)
        self._logger.Debug(f"Removed topic {topic_name}")

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
            if topic_name not in self._topics: # This may happen when the client just unsubscribed from a topic.
                self._logger.Warning(f"Update for unknown topic {topic_name}")
                continue
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
        if len(self._preview_path)>0 and change['id'] == self._preview_path[0].change.id:
            self.UndoAll(self._preview_path)
            self._preview_path = []

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

    T = TypeVar('T',bound=Topic)
    def RegisterTopic(self,topic_name,topic_type:type[T])->T:
        if topic_name in self._topics:
            topic = self._topics[topic_name]
            assert isinstance(topic,topic_type)
            return topic
        topic = self._topics[topic_name] = topic_type(topic_name,lambda name: self._topics[name],self._command_manager)
        self._SendToRouter('subscribe',topic_name=topic_name,type = topic_type.GetTypeName())
        self._logger.Debug(f"Added topic {topic_name} of type {topic_type.__name__}")
        return topic

    '''
    Shortcut functions
    '''
    def UndoAll(self,commands:List[ChangeCommand]):
        '''
        Undo all changes
        '''
        for command in reversed(commands):
            command.Undo()