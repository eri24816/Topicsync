'''
In a chat room, every topic is synced across all clients.
Clients can subscribe to a topic and receive updates when the topic is updated.
Clients can also update a topic, which will be synced to all clients.
'''

from typing import Dict, Tuple
import websockets
import asyncio
from .topic import Topic
from .service import Service
import json
from itertools import count
from chatroom import logger

class ChatroomServer:
    def __init__(self):
        self._topics :Dict[str,Topic] = {}
        self._services : Dict[str,Service] = {}
        self.client_id_count = count(1)
        self._logger = logger.Logger(logger.DEBUG)
        self._logger.Info("Chatroom server started")
        
    async def HandleClient(self,client,path):
        '''
        Handle a client connection. 
        '''
        try:
            client_id = next(self.client_id_count)
            self._logger.Info(f"Client {client_id} connected")
            await client.send(self.MakeMessage("hello",id=client_id))
            await self.Publish("_chatroom/server_status",f"[info] Client {client_id} connected")
            await self.Publish(f"_chatroom/client_message/{client_id}",f"[info] Client {client_id} connected")

            async for message in client:
                self._logger.Debug(f"> {message}")
                message_type, content = self.ParseMessage(message)
                if message_type == "publish":
                    await self.Publish(content["topic"],content["value"])
                elif message_type == "subscribe":
                    await self.Subscribe(client,content["topic"])
                elif message_type == "unsubscribe":
                    await self.Unsubscribe(client,content["topic"])
                elif message_type == "try_publish":
                    await self.TryPublish(client_id,content["topic"],content["change"])
                elif message_type == "call":
                    await self.Service(client,content["service"],content["command"],content["args"])
                elif message_type == "respond":
                    await self.Respond(content["service"],content["data"])
                else:
                    await self.Publish(f"__client_message__/{client_id}",f"[error] Unknown message type: {message['type']}")
        except websockets.exceptions.ConnectionClosed as e:
            print(e)
            self._logger.Info(f"Client {client_id} disconnected")
            await self.Publish("_chatroom/server_status",f"[info] Client {client_id} disconnected")
            # clear subscriptions
            for topic in self._topics.values():
                if client in topic.GetSubscribers():
                    topic.RemoveSubscriber(client)

    async def SendToClientRaw(self,client,message):
        '''
        Send a message to a client
        '''
        await client.send(message)
        self._logger.Debug(f"< {message}")

    async def SendToClient(self,client,*args,**kwargs):
        '''
        Send a message to a client
        '''
        await self.SendToClientRaw(client,self.MakeMessage(*args,**kwargs))
    '''
    ================================
    Client API functions 
    ================================
    '''

    async def Publish(self,topic_name,change): 
        '''
        Publish a topic and send the new value to all subscribers
        '''
        #TODO: check client version > current version
        
        if topic_name not in self._topics:
            assert change["type"] == "raw"
            topic = self._topics[topic_name] = Topic(topic_name,change["value"])
        else:
            topic = self._topics[topic_name]
            topic.Update(value)
        for subscriber in topic.GetSubscribers():
            await self.SendToClient(subscriber,"update",topic=topic_name,value=topic.Getvalue())

    async def Subscribe(self,client,topic_name):
        '''
        Add a client to a topic and send the current value to the client
        '''
        if topic_name not in self._topics:
            self._topics[topic_name] = Topic(topic_name,None)
        topic = self._topics[topic_name]
        topic.AddSubscriber(client)
        await self.SendToClient(client,"update",topic=topic_name,value=topic.Getvalue())

    async def Unsubscribe(self,client,topic_name):
        '''
        Remove a client from a topic
        '''
        topic = self._topics[topic_name]
        topic.RemoveSubscriber(client)

    async def TryPublish(self,source,topic_name,change):
        '''
        
        '''
        publish_validation_service_name = f"_chatroom/topic_validation/{topic_name}"
        if publish_validation_service_name in self._services: # if there is a validator registered
            # ask the validator to validate the change
            await self._services[publish_validation_service_name].Request(source,change)
        else: # no validator registered. publish directly
            await self.Publish(topic_name,change)

    async def Service(self,client,service_name,command,args):
        '''
        Call a service
        '''
        if service_name in self._services:
            await self._services[service_name].Request(client,command,args)
        else:
            await self.SendToClient(client,"message",message=f"Service {service_name} does not exist")

    async def Respond(self,service,data):
        '''
        receive a response from a service provider
        '''
        source = data["source"]
        await self.SendToClient(source,"respond",data=data["data"])
        
    # outbound messages
    async def RejectPublish(self,source,topic_name,change):
        await self.SendToClient(source,"reject_publish",topic=topic_name,change=change)
    
    async def Request(self,provider,source,data):
        await self.SendToClient(provider,"service",source=source,data=data)

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

    '''
    ================================
    Server functions
    ================================
    '''
    def Start(self):
        start_server = websockets.serve(self.HandleClient, "localhost", 8765)
        asyncio.get_event_loop().run_until_complete(start_server)
        asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    chat_room = ChatroomServer()
    chat_room.Start()