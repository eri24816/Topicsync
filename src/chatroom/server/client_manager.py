from __future__ import annotations
import asyncio
import json
from typing import Awaitable, Callable, Dict, List, Tuple
from itertools import count
from collections import defaultdict

from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed
from chatroom import logger
from chatroom.command import ChangeCommand

def MakeMessage(message_type,**kwargs)->str:
    return json.dumps({"type":message_type,"args":kwargs})

def ParseMessage(message_json)->Tuple[str,dict]:
    message = json.loads(message_json)
    return message["type"],message["args"]

class Client:
    def __init__(self,id,ws:WebSocketServerProtocol,logger,sending_queue:asyncio.Queue[Tuple[Client,Tuple,Dict]]):
        self.id = id
        self._ws = ws
        self._logger = logger
        self._sending_queue = sending_queue

    async def _SendRaw(self,message):
        await self._ws.send(message)
        self._logger.Debug(f"<{self.id} {message}")

    async def SendAsync(self,*args,**kwargs):
        await self._SendRaw(MakeMessage(*args,**kwargs))

    def Send(self,*args,**kwargs):
        self._sending_queue.put_nowait((self,args,kwargs))

    

class ClientManager:
    def __init__(self) -> None:
        self._logger = logger.Logger(logger.DEBUG,"CM")
        self._clients:Dict[int,Client] = {}
        self._client_id_count = count(1)
        self._message_handlers:Dict[str,Callable[...,None|Awaitable[None]]] = {'subscribe':self._HandleSubscribe,'unsubscribe':self._HandleUnsubscribe}
        self._subscriptions:defaultdict[str,set] =defaultdict(set)
        self._sending_queue:asyncio.Queue[Tuple[Client,Tuple,Dict]] = asyncio.Queue()

    async def Run(self):
        while True:
            client,args,kwargs = await self._sending_queue.get()
            try:
                await client.SendAsync(*args,**kwargs)
            except ConnectionClosed:
                self._CleanUpClient(client)

    def Send(self,client:Client,*args,**kwargs):
        self._sending_queue.put_nowait((client,args,kwargs))

    async def HandleClient(self,ws:WebSocketServerProtocol,path):
        '''
        Handle a client connection. 
        '''
        try:
            client_id = next(self._client_id_count)
            client = self._clients[client_id] = Client(client_id,ws,self._logger,self._sending_queue)
            self._logger.Info(f"Client {client_id} connected")
            await client.SendAsync("hello",id=client_id)

            async for message in ws:
                self._logger.Debug(f"> {message}")
                message_type, args = ParseMessage(message)
                if message_type in self._message_handlers:
                    return_value = self._message_handlers[message_type](sender = client,**args)
                    if isinstance(return_value,Awaitable):
                        await return_value
                else:
                    self._logger.Error(f"Unknown message type: {message_type}")
                    pass

        except ConnectionClosed as e:
            self._logger.Info(f"Client {client_id} disconnected: {e.with_traceback(e.__traceback__)}")
            self._CleanUpClient(client)
        except Exception as e:
            self._logger.Error(f"Error handling client {client_id}: {e.with_traceback(e.__traceback__)}")
            self._CleanUpClient(client)

    def SendUpdate(self,changes:List[ChangeCommand]):
        '''
        Broadcast a list of changes to all clients subscribed to the topics in the changes.
        '''
        messages_for_client = defaultdict(list)
        for change in changes:
            for client_id in self._subscriptions[change.topic_name]:
                messages_for_client[client_id].append(change.Serialize())

        for client_id in messages_for_client:
            client = self._clients[client_id]
            self.Send(client,"update",changes=messages_for_client[client_id])
    
    def RegisterMessageHandler(self,message_type:str,handler:Callable[...,None|Awaitable[None]]):
        self._message_handlers[message_type] = handler

    def _CleanUpClient(self,client:Client):
        for topic in self._subscriptions:
            self._subscriptions[topic].discard(client.id)

    def _HandleSubscribe(self,sender:Client,topic_name:str):
        self._subscriptions[topic_name].add(sender.id)
        self._logger.Info(f"Client {sender.id} subscribed to {topic_name}")

    def _HandleUnsubscribe(self,sender:Client,topic_name:str):
        self._subscriptions[topic_name].discard(sender.id)
        