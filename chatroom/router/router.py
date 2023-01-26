'''
In a chat room, every topic is synced across all clients.
Clients can subscribe to a topic and receive updates when the topic is updated.
Clients can also update a topic, which will be synced to all clients.
'''

import queue
import threading
from typing import TYPE_CHECKING, Callable, Dict, List, Tuple
import uuid
import websockets
import asyncio
from chatroom.router.endpoint import Endpoint, WSEndpoint

from chatroom.utils import EventManager
from chatroom.topic_change import SetChange

from .topic import CreateTopic, Topic
from .service import Service, Request
import json
from itertools import count
from chatroom import logger
from chatroom.utils import ParseMessage

from websockets import exceptions as ws_exceptions

from chatroom.topic_change import InvalidChangeException

class ChatroomRouter:

    def __init__(self,server,port=8765,start_thread = True, log_prefix = "Server"):
        self._port = port
        self._topics :Dict[str,Topic] = {}
        self._services : Dict[str,Service] = {}
        self._client_id_count = count(1)
        self._endpoints : Dict[int,Endpoint] = {0:server}
        self._logger = logger.Logger(logger.DEBUG,prefix=log_prefix)
        self._evnt = EventManager()
        
        self._message_handlers:Dict[str,Callable] = {}
        for message_type in ['request','response','register_service','unregister_service','subscribe','update','unsubscribe']:
            self._message_handlers[message_type] = getattr(self,'handle_'+message_type)
        
        self._thread = None

        if start_thread:
            self.StartThread()

    def __del__(self):
        print("Router deleted")
        self.Stop()
        
    async def _HandleClient(self,ws,path):
        '''
        Handle a client connection. 
        '''
        client = WSEndpoint(ws,self._logger)
        try:
            client_id = next(self._client_id_count)
            self._endpoints[client_id] = client
            self._logger.Info(f"Client {client_id} connected")
            await client.Send("hello",id=client_id)

            async for message in ws:
                self._logger.Debug(f"> {message}")
                message_type, args = ParseMessage(message)
                if message_type in self._message_handlers:
                    await self._message_handlers[message_type](client = client,**args)
                else:
                    self._logger.Error(f"Unknown message type: {message_type}")
                    pass

        except ws_exceptions.ConnectionClosed as e:
            print(e)
            self._logger.Info(f"Client {client_id} disconnected")
            # clear subscriptions
            for topic in self._topics.values():
                if client in topic.GetSubscribers():
                    topic.RemoveSubscriber(client)
            del self._endpoints[client_id]

    '''
    ================================
    Internal API functions 
    ================================
    '''

    async def handle_request(self,client,service_name,args,request_id):
        '''
        Request a service. The server forwards the request to the service provider.
        '''
        # forward the request to the service provider, and wait for the response
        response = await self._MakeRequest(service_name=service_name,**args)

        # forward the response back to the client
        await client.Send("response",response=response,request_id=request_id)

    async def handle_response(self,client,response,request_id):
        '''
        Response to a service request. The server forwards the response to the client.
        '''
        self._evnt.Resume(f'response_waiter{request_id}',response)

    async def handle_register_service(self,client,service_name):
        self._services[service_name] = Service(service_name,client)

    async def handle_unregister_service(self,client,service_name):
        if service_name not in self._services:
            self._logger.Error(f"Service {service_name} not registered")
            return
        if self._services[service_name].provider != client:
            self._logger.Error(f"Client {client} is not the provider of service {service_name}")
            return
        del self._services[service_name]

    async def handle_subscribe(self,client,topic_name,type):
        '''
        The client wants to access a topic. 
        Since the client may not know if the topic exists, the server creates the topic if it's not. 
        The new topic's type is determined with the type argument provided in this message.
        After the topic is created (or if it already exists), the client is subscribed to the topic.
        '''
        #TODO: validate creation
        
        if topic_name not in self._topics:
            # create the topic
            topic = self._topics[topic_name] = CreateTopic(topic_name,type)
            self._logger.Info(f"Created topic {topic_name} of type {type}")

            # subscribe the client to the topic
            topic.AddSubscriber(client)
            await client.Send("update",topic_name=topic_name,change=SetChange(topic.Getvalue()).Serialize())

            # since the topic has no value yet, no update is sent to the client
        else:
            topic = self._topics[topic_name]

            # subscribe the client to the topic and send the current value to the client
            topic.AddSubscriber(client)
            await client.Send("update",topic_name=topic_name,change=SetChange(topic.Getvalue()).Serialize())

    #TODO async def _delete_topic(self,client,topic_name):

    async def handle_update(self,client,topic_name,change):
        '''
        Try to update a topic. The server first request the '_chatroom/validate_change' service to validate the change, then
        - forwards the update to all subscribers, if the change is valid
        - sends 'reject_update' message to the client, if the change is invalid
        If there is no '_chatroom/validate_change' service registered, the server will always accept the change.
        '''
        if topic_name not in self._topics:
            self._logger.Error(f"Topic {topic_name} does not exist")
            return
        
        # validate the change
        if f'_chatroom/validate_change/{topic_name}' in self._services:
            response = await self._MakeRequest(f'_chatroom/validate_change/{topic_name}',change=change)
            assert response
            if not response['valid']:
                await client.Send("reject_update",topic_name=topic_name,change=change,reason=response['reason'] if 'reason' in response else 'unknown')
                return

        topic = self._topics[topic_name]
        try:
            topic.ApplyChange(change)
        except InvalidChangeException as e:
            print(e)
            # notify the client that the update is rejected
            await client.Send("reject_update",topic_name=topic_name,change=change,reason=str(e))
            return
        #topic.ApplyChange(change)
        
        # notify all subscribers
        for client in topic.GetSubscribers():
            await client.Send("update",topic_name=topic_name,change=change)
        

    async def handle_unsubscribe(self,client,topic_name):
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
    
    async def _MakeRequest(self,service_name,**args):
        '''
        Send a request to a service provider and wait for the response
        '''
        provider = self._services[service_name].provider
        request_id = str(uuid.uuid4())
        await provider.Send("request",service_name=service_name,args=args,request_id=request_id)
        response = await self._evnt.Wait(f'response_waiter{request_id}')
        return response

    '''
    ================================
    Public functions
    ================================
    '''
    def Start(self):
        '''
        Bloking function that starts the server
        '''
        asyncio.set_event_loop(asyncio.new_event_loop())
        start_server = websockets.serve(self._HandleClient, "localhost", self._port) # type: ignore
        self._logger.Info("Chatroom server started")
        asyncio.get_event_loop().run_until_complete(start_server)
        asyncio.get_event_loop().run_forever()

    def StartThread(self):
        '''
        Starts the server in a new thread
        '''
        self._thread = threading.Thread(target=self.Start)
        self._thread.daemon = True
        self._thread.start()

    def Stop(self):
        '''
        Stops the server
        '''
        if self._thread is not None:
            self._thread.join()

if __name__ == "__main__":
    chatroom = ChatroomRouter()
    chatroom.Start()