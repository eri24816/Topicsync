import queue
import uuid
from typing import TYPE_CHECKING, Callable, Dict, List, Tuple, Type, TypeVar
import websockets
import asyncio
import json
from collections import defaultdict
from chatroom import logger
import threading

from chatroom.topic import StringTopic, Topic
from chatroom.client.request import Request
from chatroom.utils import MakeMessage, ParseMessage
from chatroom.command import CommandManager

# to stop pylance complaning
from websockets.client import connect as ws_connect

class ChatroomClient:
    message_types = []
    def __init__(self,host="localhost",port=8765,start=False,log_prefix="client"):
        self._host = f'ws://{host}:{port}'
        self._topics:Dict[str,Topic] = {}
        self._command_manager = CommandManager(on_recording_stop=self._OnRecordingStop)
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
        self.connected_event.set()
        self._sending_queue = asyncio.Queue(loop=self._event_loop)
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

    def _SendToServer(self,*args,**kwargs):
        '''
        Send a message to the server
        '''
        message = MakeMessage(*args,**kwargs)
        self._SendToServerRaw(message)

    def _OnRecordingStop(self,commands):
        '''
        Called when the command manager stops recording
        '''
        #TODO: send commands to server
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
        self._SendToServer("response",response = response,request_id = request_id)

    def _handle_response(self,request_id,response):
        '''
        Handle a response from another client
        '''
        request = self.request_pool.pop(request_id)
        request.on_response(response)

    def _handle_update(self,topic_name,change):
        '''
        Handle an update message from the server
        '''
        topic = self._topics[topic_name]
        change = topic.DeserializeChange(change)
        if change.id == self._command_manager.recorded_commands[0].change.id:
            self._command_manager.recorded_commands.pop(0)
        else:
            self._command_manager.Reset()
            topic.ApplyChange(change)

    def _handle_reject_update(self,topic_name,change,reason):
        '''
        Handle a rejected update from the server
        '''
        self._logger.Warning(f"Update rejected for topic {topic_name}: {reason}")
        recorded = self._command_manager.recorded_commands
        if len(recorded)>0 and change.id == recorded[0].change.id:
            self._command_manager.Reset()


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

    T = TypeVar('T',bound=Topic)
    def RegisterTopic(self,type:Type[T],topic_name)->T:
        '''
        Returns a topic object for user-side use.
        The method will send "subscribe" message to the server if the topic is not in the client yet.
        If the topic is already created in the server, the server will send an update message to the client.
        If the topic is not created in the server, the server will create the topic and send an update message to the client.
        Note that the newly created topic will have a default value until the server sends back the update message.
        '''
        if topic_name in self._topics:
            topic = self._topics[topic_name]
            assert isinstance(topic,type)
            return topic
        
        topic = type(topic_name,self)
        
        self._topics[topic_name] = topic
        self._SendToServer("subscribe",topic_name=topic_name,type=topic.GetTypeName())
        return topic
    
    def DeleteTopic(self,topic_name):
        '''
        Delete a topic
        '''
        self._SendToServer("delete_topic",topic_name=topic_name)

    def MakeRequest(self,service_name:str,args:Dict,on_response:Callable):
        '''
        Request a service from another client. Does not wait for the response.
        '''
        id = str(uuid.uuid4())
        request = Request(id,on_response)
        self.request_pool[id] = request
        self._SendToServer("request",service_name=service_name,args=args,request_id=id)
        return request

    def RegisterService(self,service_name:str,service:Callable):
        '''
        Register a service
        '''
        self.service_pool[service_name] = service
        self._SendToServer("register_service",service_name=service_name)

    # called by the topic class =================================

    def UpdateSingle(self,topic_name,change):
        '''
        Update a topic.
        '''
        changes = [{'topic_name':topic_name,'change':change}]
        self._SendToServer("client_update",changes=changes)

    def Unsubscribe(self,topic_name):
        '''
        Unsubscribe from a topic
        '''
        self._SendToServer("unsubscribe",topic_name=topic_name)
        self._topics.pop(topic_name)

