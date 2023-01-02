from typing import Dict, List, Tuple
import websockets
import asyncio
import json
from collections import defaultdict
from chatroom import logger
import threading

from chatroom.client.topic import Topic, TopicChange

class ChatroomClient:
    def __init__(self,host):
        self._host = host
        self._topics:Dict[str,Topic] = {}
        self._client_id = None
        self._message_handlers = {
            "hello":self._HandleHello,
            "update":self._HandleUpdate,
        }
        self._logger = logger.Logger(logger.DEBUG)

    def _ThreadedRun(self):
        '''
        Run the client in a new thread
        '''
        self._event_loop = asyncio.new_event_loop()
        self._sending_queue = asyncio.Queue(loop=self._event_loop)
        self._event_loop.run_until_complete(self._Connect())
        self.connected_event.set()
        self._event_loop.run_until_complete(self._Run())

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
    def Disconnect(self):
        '''
        Disconnect from the server
        '''
        asyncio.run(self._ws.close())

    async def _ReceivingLoop(self):
        '''
        Client loop
        '''
        async for message in self._ws:
            self._logger.Debug(f"> {message}")  
            await self._HandleMessage(message)

    async def _SendingLoop(self):
        '''
        Sending loop
        '''
        while True:
            message = await self._sending_queue.get()
            await self._ws.send(message)
            self._logger.Debug(f"< {message}")

    async def _HandleMessage(self,message):
        '''
        Handle a message from the server
        '''
        message_type,message_content = self.ParseMessage(message)
        await self._message_handlers[message_type](message_content)

    def SendToServerRaw(self,message):
        '''
        Send a raw message to the server
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
    async def _HandleHello(self,message_content):
        '''
        Handle a hello message from the server
        '''
        self._client_id = message_content["id"]
        self._logger.Info(f"Connected to server as client {self._client_id}")

    async def _HandleUpdate(self,message_content):
        '''
        Handle an update message from the server
        '''
        topic_name = message_content["topic"]
        change = TopicChange(message_content["change"])
        source = message_content["source"]

        self._topics[topic_name].Update(change,source)

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

    '''
    ================================
    Helper functions
    ================================
    '''

    def MakeMessage(self,type,*args,**kwargs)->str:
        if len(args) == 1:
            content = args[0]
        else:
            content = kwargs
        return json.dumps({"type":type,"content":content})

    def ParseMessage(self,message_json)->Tuple[str,dict]:
        message = json.loads(message_json)
        return message["type"],message["content"]