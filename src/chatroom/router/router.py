'''
In a chat room, every topic is synced across all clients.
Clients can subscribe to a topic and receive updates when the topic is updated.
Clients can also update a topic, which will be synced to all clients.
'''

from collections import defaultdict
import queue
import threading
from typing import TYPE_CHECKING, Callable, Dict, List, Tuple
import uuid
import websockets
import asyncio
from chatroom.router.endpoint import Endpoint, WSEndpoint

from chatroom.utils import EventManager
from chatroom.topic_change import SetChange

from chatroom.topic import TopicFactory, Topic, SetTopic
from .service import Service, Request
import json
from itertools import count
from chatroom import logger
from chatroom.utils import ParseMessage

from websockets import exceptions as ws_exceptions

from chatroom.topic_change import InvalidChangeException


from chatroom.router.endpoint import PythonEndpoint

class ChatroomRouter:

    def __init__(self,server:PythonEndpoint,port=8765,start_thread = True, log_prefix = "Router"):
        self._server = server
        self._port = port
        self._topics : Dict[str,Topic] = {}
        self._services : Dict[str,Service] = {}
        self._client_id_count = count(1)
        self._endpoints : Dict[int,Endpoint] = {0:server}
        self._logger = logger.Logger(logger.DEBUG,prefix=log_prefix)
        self._evnt = EventManager()
        
        self._message_handlers:Dict[str,Callable] = {}
        for message_type in ['request','response','register_service','unregister_service','subscribe','client_update','unsubscribe','update','reject_update']:
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
        try:
            client_id = next(self._client_id_count)
            client = WSEndpoint(client_id,ws,self._logger)
            self._endpoints[client_id] = client
            client.id = client_id
            self._logger.Info(f"Client {client_id} connected")
            await client.Send("hello",id=client_id)

            async for message in ws:
                self._logger.Debug(f"> {message}")
                message_type, args = ParseMessage(message)
                if message_type in self._message_handlers:
                    await self._message_handlers[message_type](sender = client,**args)
                else:
                    self._logger.Error(f"Unknown message type: {message_type}")
                    pass

        except ws_exceptions.ConnectionClosed as e:
            self._logger.Info(f"Client {client_id} disconnected: {e.with_traceback(e.__traceback__)}")
            self._CleanUpClient(client)
        except Exception as e:
            self._logger.Error(f"Error handling client {client_id}: {e.with_traceback(e.__traceback__)}")

    async def _ServerReceiveLoop(self):
        while True:
            message = await self._server.queue_to_router.get()
            self._logger.Debug(f"> {message}")
            message_type, args = ParseMessage(message)
            if message_type in self._message_handlers:
                await self._message_handlers[message_type](sender = self._server,**args)
            else:
                self._logger.Error(f"Unknown message type: {message_type}")
                pass

    def _CleanUpClient(self,client:Endpoint):
        # clear subscriptions
        for topic in self._topics.values():
            if client in topic.subscribers:
                topic.subscribers.remove(client)
        # clear services
        for service_name,service in self._services.copy().items():
            if client == service.provider:
                self._logger.Debug(f"Service {service_name} unregistered")
                del self._services[service_name]
        del self._endpoints[client.id]
    '''
    ================================
    Internal API functions 
    ================================
    '''

    async def handle_request(self,sender,service_name,args,request_id):
        '''
        Request a service. The server forwards the request to the service provider.
        '''
        # forward the request to the service provider, and wait for the response
        response = await self._MakeRequest(service_name=service_name,**args)

        # forward the response back to the client
        await self._SendToEndpoint(sender,"response",response=response,request_id=request_id)

    async def handle_response(self,sender,response,request_id):
        '''
        Response to a service request. The server forwards the response to the client.
        '''
        self._evnt.Resume(f'response_waiter{request_id}',response)

    async def handle_register_service(self,sender,service_name):
        self._services[service_name] = Service(service_name,sender)

    async def handle_unregister_service(self,sender,service_name):
        if service_name not in self._services:
            self._logger.Error(f"Service {service_name} not registered")
            return
        if self._services[service_name].provider != sender:
            self._logger.Error(f"Client {sender} is not the provider of service {service_name}")
            return
        del self._services[service_name]

    async def handle_subscribe(self,sender,topic_name,type):
        if topic_name not in self._topics:
            topic = self._topics[topic_name] = TopicFactory(topic_name,type)
            topic.subscribers.append(sender)
        else:
            topic = self._topics[topic_name]
            topic.subscribers.append(sender)
            if type != topic.GetTypeName():
                self._logger.Error(f"Topic {topic_name} already exists with a different type")
                return
        await self._SendToEndpoint(sender,"update",changes=[{'topic_name':topic_name,'change':SetChange(topic.GetValue()).Serialize()}])

    async def handle_client_update(self,sender,changes):
        
        for item in changes:
            topic_name = item['topic_name']
            if topic_name not in self._topics:
                self._logger.Error(f"Topic {topic_name} does not exist")
                return
        
        forward_list = []
        reflect_list = []

        for item in changes:
            topic_name = item['topic_name']
            topic = self._topics[topic_name]
            if self._server in topic.subscribers:
                forward_list.append(item)
            else:
                reflect_list.append(item)
        
        if len(forward_list) > 0:
            await self._server.Send("client_update",client_id=sender.id,changes = forward_list)
        
        if len(reflect_list) > 0:
            await self.handle_update(None,reflect_list)
        

    async def handle_unsubscribe(self,sender,topic_name):
        '''
        Remove a client from a topic subscription.
        '''
        topic = self._topics[topic_name]
        topic.subscribers.remove(sender)
        if len(topic.subscribers) == 0:
            del self._topics[topic_name]

    async def handle_reject_update(self,sender,client_id,topic_name,change,reason):
        '''
        The server rejects the update. The client should handle this message.
        '''
        client = self._endpoints[client_id]
        await self._SendToEndpoint(client,"reject_update",topic_name=topic_name,change=change,reason=reason)

    async def handle_update(self,sender,changes):
        '''
        The server forwards an update to the client. The client should handle this message.
        '''
        for item in changes:
            topic_name = item['topic_name']
            change_dict = item['change']
            topic = self._topics[topic_name]
            change = topic.DeserializeChange(change_dict)
            topic.ApplyChange(change)
            for client in topic.subscribers:
                if client == self._server:
                    continue
                await self._SendToEndpoint(client,"update",changes = [item]) #TODO: optimize this

    '''
    ================================
    Helper functions
    ================================
    '''
    
    async def _MakeRequest(self,service_name,**args):
        '''
        Send a request to a service provider and wait for the response
        '''
        if service_name not in self._services:
            self._logger.Warning(f"Service {service_name} not registered")
            return
        provider = self._services[service_name].provider
        request_id = str(uuid.uuid4())
        await self._SendToEndpoint(provider,"request",service_name=service_name,args=args,request_id=request_id)
        response = await self._evnt.Wait(f'response_waiter{request_id}')
        return response
    
    async def _SendToEndpoint(self,endpoint,message_type,**args):
        '''
        Send a message to an endpoint
        '''
        try:
            await endpoint.Send(message_type,**args)
        except ws_exceptions.ConnectionClosed as e:
            self._logger.Warning(f"Connection to {endpoint} closed")
            self._CleanUpClient(endpoint)
    '''
    ================================
    Public functions
    ================================
    '''
    def Start(self,started_event = None):
        '''
        Bloking function that starts the server
        '''
        asyncio.set_event_loop(asyncio.new_event_loop())
        self._server.SetEventLoop(asyncio.get_event_loop())
        start_router = websockets.serve(self._HandleClient, "localhost", self._port) # type: ignore
        start = asyncio.gather(start_router,self._ServerReceiveLoop())
        self._logger.Info("Chatroom server started")
        if started_event is not None:
            started_event.set()
        asyncio.get_event_loop().run_until_complete(start)
        asyncio.get_event_loop().run_forever()

    def StartThread(self):
        '''
        Starts the server in a new uwu thread
        '''
        started = threading.Event()
        self._thread = threading.Thread(target=self.Start,kwargs={'started_event':started})
        self._thread.daemon = True
        self._thread.start()
        started.wait()

    def Stop(self):
        '''
        Stops the server
        '''
        if self._thread is not None:
            self._thread.join()