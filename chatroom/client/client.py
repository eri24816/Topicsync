import queue
import uuid
from typing import Callable, Dict, List, Tuple, Type, TypeVar
import websockets
import asyncio
import json
from collections import defaultdict
from chatroom import logger
import threading

from chatroom.client.topic import StringTopic, Topic
from chatroom.client.request import Request

class ChatroomClient:
    message_types = []
    def __init__(self,host="localhost",port=8765,start=False,log_prefix="client"):
        self._host = f'ws://{host}:{port}'
        self._topics:Dict[str,Topic] = {}
        self._client_id = None
        self._logger = logger.Logger(logger.DEBUG,prefix=log_prefix)
        self.request_pool:Dict[str,Request] = {}
        self.service_pool:Dict[str,Callable] = {}

        self._message_handlers:Dict[str,Callable] = {}
        for message_type in ['hello','update','request','response','reject_update']:
            self._message_handlers[message_type] = getattr(self,'_'+message_type)

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
        self._ws = await websockets.connect(self._host)

    async def _ReceivingLoop(self):
        '''
        Receiving loop
        '''
        async for message in self._ws:
            self._logger.Debug(f"> {message}")  
            message_type,args = self.ParseMessage(message)
            if message_type in self._message_handlers:
                self._message_handlers[message_type](**args)
            else:
                self._logger.Warning(f"Unknown message type {message_type}")

    async def _SendingLoop(self):
        '''
        Sending loop
        '''
        while True:
            message = await self._sending_queue.get()
            await self._ws.send(message)
            self._logger.Debug(f"< {message}")

    def _SendToServerRaw(self,message):
        '''
        Send a raw string to the server
        '''
        self._event_loop.call_soon_threadsafe(self._sending_queue.put_nowait,message)

    def _SendToServer(self,*args,**kwargs):
        '''
        Send a message to the server
        '''
        message = self.MakeMessage(*args,**kwargs)
        self._SendToServerRaw(message)

    '''
    ================================
    Client API receive functions
    ================================
    '''

    def _hello(self,id):
        '''
        Handle a hello message from the server
        '''
        self._client_id = id
        self._logger.Info(f"Connected to server as client {self._client_id}")

    def _update(self,topic_name,change):
        '''
        Handle an update message from the server
        '''
        self._topics[topic_name].Update(change) # The topic will handle the update and call the callbacks

    def _request(self,service_name,args,request_id):
        '''
        Handle a request from another client
        '''
        response = self.service_pool[service_name](**args)
        self._SendToServer("response",response = response,request_id = request_id)

    def _response(self,request_id,response):
        '''
        Handle a response from another client
        '''
        request = self.request_pool.pop(request_id)
        request.on_response(response)

    def _reject_update(self,topic_name,change,reason):
        '''
        Handle a rejected update from the server
        '''
        self._logger.Warning(f"Update rejected for topic {topic_name}: {reason}")
        self._topics[topic_name].UpdateRejected(change)

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

    def GetID(self):
        '''
        Get the client ID
        '''
        return self._client_id

    T = TypeVar('T',bound=Topic)
    def RegisterTopic(self,type:Type[T],topic_name)->T:
        '''
        Returns a topic object for user-side use.
        The method will send "register_topic" to the server if the topic is not in the client yet.
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

    def Update(self,topic_name,change):
        '''
        Update a topic
        '''
        self._SendToServer("update",topic_name=topic_name,change=change)

    def Subscribe(self,topic_name,type): #? deprecated?
        '''
        Subscribe to a topic
        '''
        self._SendToServer("subscribe",topic_name=topic_name,type=type)

    def Unsubscribe(self,topic_name):
        '''
        Unsubscribe from a topic
        '''
        self._SendToServer("unsubscribe",topic_name=topic_name)

    '''
    ================================
    Helper functions
    ================================
    '''

    def MakeMessage(self,message_type,**kwargs)->str:
        return json.dumps({"type":message_type,"args":kwargs})

    def ParseMessage(self,message_json)->Tuple[str,dict]:
        message = json.loads(message_json)
        return message["type"],message["args"]