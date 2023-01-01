'''
In a chat room, every topic is synced across all clients.
Clients can subscribe to a topic and receive updates when the topic is updated.
Clients can also update a topic, which will be synced to all clients.
'''

from typing import Tuple
import websockets
import asyncio
from .topic import Topic
import json
from itertools import count
from chatroom import logger

class ChatroomServer:
    def __init__(self):
        self._topics = {}
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
                    await self.Publish(content["topic"],content["payload"])
                elif message_type == "subscribe":
                    await self.Subscribe(client,content["topic"])
                elif message_type == "unsubscribe":
                    await self.Unsubscribe(client,content["topic"])
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

    async def SendToClient(self,client,message):
        '''
        Send a message to a client
        '''
        await client.send(message)
        self._logger.Debug(f"< {message}")
    '''
    ================================
    Client API functions 
    ================================
    '''

    async def Publish(self,topic_name,payload): 
        '''
        Publish a topic and send the new payload to all subscribers
        '''
        #TODO: check client version > current version
        if topic_name not in self._topics:
            topic = self._topics[topic_name] = Topic(topic_name,payload)
        else:
            topic = self._topics[topic_name]
            topic.Update(payload)
        for subscriber in topic.GetSubscribers():
            message = self.MakeMessage("update",topic=topic_name,payload=topic.GetPayload())
            await self.SendToClient(subscriber,message)

    async def Subscribe(self,client,topic_name):
        '''
        Add a client to a topic and send the current payload to the client
        '''
        if topic_name not in self._topics:
            self._topics[topic_name] = Topic(topic_name,None)
        topic = self._topics[topic_name]
        topic.AddSubscriber(client)
        await self.SendToClient(client,self.MakeMessage("update",topic=topic_name,payload=topic.GetPayload()))

    async def Unsubscribe(self,client,topic_name):
        '''
        Remove a client from a topic
        '''
        topic = self._topics[topic_name]
        topic.RemoveSubscriber(client)


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