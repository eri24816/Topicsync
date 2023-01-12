import queue
import random
from typing import Callable, Dict, List, Tuple
import websockets
import asyncio
import json
from collections import defaultdict
from chatroom import logger
import threading

from chatroom.client.topic import Topic, TopicChange
from chatroom.client.request import Request

class ChatroomClient:
    message_types = []
    def __init__(self,host):
        self._host = host
        self._topics:Dict[str,Topic] = {}
        self._client_id = None
        self._logger = logger.Logger(logger.DEBUG)
        self.request_pool:Dict[int,Request] = {}
        self.service_pool:Dict[str,Callable] = {}

        self._message_handlers:Dict[str,Callable] = {}
        for message_type in ['hello','update','request','response']:
            self._message_handlers[message_type] = getattr(self,'_'+message_type)

    def _ThreadedRun(self):
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

    def _Disconnect(self):
        '''
        Disconnect from the server
        '''
        asyncio.run(self._ws.close())

    async def _ReceivingLoop(self):
        '''
        Receiving loop
        '''
        async for message in self._ws:
            self._logger.Debug(f"> {message}")  
            message_type,content = self.ParseMessage(message)
            if message_type in self._message_handlers:
                self._message_handlers[message_type](**content)
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

    def SendToServerRaw(self,message):
        '''
        Send a raw string to the server
        '''
        self._sending_queue.put_nowait(message)

    def SendToServer(self,*args,**kwargs):
        '''
        Send a message to the server
        '''
        message = self.MakeMessage(*args,**kwargs)
        self.SendToServerRaw(message)

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

    def _update(self,topic_name,change,source):
        '''
        Handle an update message from the server
        '''
        change = TopicChange(change)
        self._topics[topic_name].Update(change,source)

    def _request(self,service_name,args,request_id):
        '''
        Handle a request from another client
        '''
        response = self.service_pool[service_name](**args)
        self.SendToServer("response",response = response,request_id = request_id)

    def _response(self,request_id,response):
        '''
        Handle a response from another client
        '''
        request = self.request_pool.pop(request_id)
        request.on_response(response)

    '''
    ================================
    Public functions
    ================================
    '''

    def Run(self):
        '''
        Run the client
        '''
        self.connected_event =threading.Event()
        self.thread = threading.Thread(target=self._ThreadedRun)
        self.thread.daemon = True
        self.thread.start()
        self.connected_event.wait()

    def GetID(self):
        '''
        Get the client ID
        '''
        return self._client_id

    def AddTopicHandler(self,topic_name,handler):
        '''
        Add a handler for a topic
        '''
        if topic_name not in self._topics:
            topic = self._topics[topic_name] = Topic(self,topic_name)
            topic.AddListener(handler)

    def RemoveTopicHandler(self,topic_name,handler):
        '''
        Remove a handler for a topic
        '''
        assert topic_name in self._topics
        self._topics[topic_name].RemoveListener(handler)

    def Publish(self,topic_name,value):
        '''
        Publish a topic
        '''
        self.SendToServer("publish",topic=topic_name,value=value)

    # interface with Topic class
    def TryPublish(self,topic:Topic,change:TopicChange):
        '''
        Try to update a topic
        '''
        self.SendToServer("try_publish",source=self.GetID(),topic=topic.GetName(),change=change.Serialize())

    def Subscribe(self,topic_name):
        '''
        Subscribe to a topic
        '''
        self.SendToServer("subscribe",topic=topic_name)

    def Unsubscribe(self,topic_name):
        '''
        Unsubscribe from a topic
        '''
        self.SendToServer("unsubscribe",topic=topic_name)

    def MakeRequest(self,service_name:str,args:Dict,on_response:Callable):
        '''
        Request a service from another client
        '''
        id = random.randint(0,1000000)
        request = Request(id,on_response)
        self.request_pool[id] = request
        self.SendToServer("request",service_name=service_name,args=args,request_id=id)
        return request

    def RegisterService(self,service_name:str,service:Callable):
        '''
        Register a service
        '''
        self.service_pool[service_name] = service
        self.SendToServer("register_service",service_name=service_name)

    '''
    ================================
    Helper functions
    ================================
    '''

    def MakeMessage(self,type,**kwargs)->str:
        return json.dumps({"type":type,"content":kwargs})

    def ParseMessage(self,message_json)->Tuple[str,dict]:
        message = json.loads(message_json)
        return message["type"],message["content"]