from typing import Tuple
import websockets
import asyncio
import json
from collections import defaultdict
from chatroom import logger
import threading

class ChatroomClient:
    def __init__(self,host):
        self._host = host
        self._topics = {}
        self._client_id = None
        self._message_handlers = {
            "hello":self._HandleHello,
            "update":self._HandleUpdate,
        }
        self._topic_handlers = defaultdict(list)
        self._logger = logger.Logger(logger.DEBUG)

    def Run(self):
        '''
        Run the client
        '''
        self.connected_event =threading.Event()
        self.thread = threading.Thread(target=self._ThreadedRun)
        self.thread.daemon = True
        self.thread.start()
        self.connected_event.wait()

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
    def SendToServer(self,message):
        '''
        Send a message to the server
        '''
        self._sending_queue.put_nowait(message)

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
        payload = message_content["payload"]
        assert topic_name in self._topic_handlers
        for handler in self._topic_handlers[topic_name]:
            handler(payload)

    '''
    ================================
    Public functions
    ================================
    '''

    def AddTopicHandler(self,topic_name,handler):
        '''
        Add a handler for a topic
        '''
        if len(self._topic_handlers[topic_name])==0:
            self.SendToServer(self.MakeMessage("subscribe",topic=topic_name))
        self._topic_handlers[topic_name].append(handler)

    def RemoveTopicHandler(self,topic_name,handler):
        '''
        Remove a handler for a topic
        '''
        self._topic_handlers[topic_name].remove(handler)
        if len(self._topic_handlers[topic_name])==0:
            self.SendToServer(self.MakeMessage("unsubscribe",topic=topic_name))

    def Publish(self,topic_name,payload):
        '''
        Publish a topic
        '''
        self.SendToServer(self.MakeMessage("publish",topic=topic_name,payload=payload))

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