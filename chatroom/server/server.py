'''
In a chat room, every topic is synced across all clients.
Clients can subscribe to a topic and receive updates when the topic is updated.
Clients can also update a topic, which will be synced to all clients.
'''

from collections import defaultdict
import queue
import threading
from typing import Callable, Dict, List, Tuple
import uuid
import websockets
import asyncio

from chatroom.server.event_manager import EventManager
from chatroom.topic_change import ChangeSet

from .topic import CreateTopic, Topic
from .service import Service, Request
import json
from itertools import count
from chatroom import logger

class ChatroomServer:
    @staticmethod
    def Handler(method, name=None):
        '''
        Decorator for a handler
        '''
        if name is None:
            name = method.__name__
            if name.startswith("_"):
                name = name[1:]
        method.__self__._message_handlers[name] = method
        return method

    def __init__(self,port=8765,start_thread = False, log_prefix = "Server"):
        self._port = port
        self._topics :Dict[str,Topic] = {}
        self._services : Dict[str,Service] = {}
        self.client_id_count = count(1)
        self._clients : Dict[int,websockets.WebSocketServerProtocol] = {}
        self._logger = logger.Logger(logger.DEBUG,prefix=log_prefix)
        self._sending_queue = queue.Queue()
        self._evnt = EventManager()
        
        self._message_handlers:Dict[str,Callable] = {}
        for message_type in ['request','response','register_service','unregister_service','subscribe','update','unsubscribe']:
            self._message_handlers[message_type] = getattr(self,'_'+message_type)
        
        self._thread = None


        if start_thread:
            self.StartThread()
        
    async def HandleClient(self,client,path):
        '''
        Handle a client connection. 
        '''
        try:
            client_id = next(self.client_id_count)
            self._clients[client_id] = client
            self._logger.Info(f"Client {client_id} connected")
            await self._SendToClient(client,"hello",id=client_id)

            async for message in client:
                self._logger.Debug(f"> {message}")
                message_type, args = self.ParseMessage(message)
                if message_type in self._message_handlers:
                    await self._message_handlers[message_type](client = client,**args)
                else:
                    self._logger.Error(f"Unknown message type: {message_type}")
                    pass

        except websockets.exceptions.ConnectionClosed as e:
            print(e)
            self._logger.Info(f"Client {client_id} disconnected")
            # clear subscriptions
            for topic in self._topics.values():
                if client in topic.GetSubscribers():
                    topic.RemoveSubscriber(client)
            del self._clients[client_id]

    async def _SendToClientRaw(self,client,message):
        '''
        Send a message to a client
        '''
        await client.send(message)
        self._logger.Debug(f"< {message}")

    async def _SendToClient(self,client,*args,**kwargs):
        '''
        Send a message to a client
        '''
        await self._SendToClientRaw(client,self.MakeMessage(*args,**kwargs))

    async def _SendToClients(self,clients,*args,**kwargs):
        '''
        Send a message to a list of clients
        '''
        corountines = []
        for subscriber in clients:
            corountines.append(self._SendToClient(subscriber,*args,**kwargs))
        await asyncio.gather(*corountines)
    '''
    ================================
    Client API functions 
    ================================
    '''

    async def _request(self,client,service_name,args,request_id):
        '''
        Request a service. The server forwards the request to the service provider.
        '''
        # forward the request to the service provider, and wait for the response
        response = await self._MakeRequest(service_name=service_name,**args)

        # forward the response back to the client
        await self._SendToClient(client,"response",response=response,request_id=request_id)

    async def _response(self,client,response,request_id):
        '''
        Response to a service request. The server forwards the response to the client.
        '''
        self._evnt.Resume(f'response_waiter{request_id}',response)

    async def _register_service(self,client,service_name):
        self._services[service_name] = Service(service_name,client)

    async def _unregister_service(self,client,service_name):
        if service_name not in self._services:
            self._logger.Error(f"Service {service_name} not registered")
            return
        if self._services[service_name].provider != client:
            self._logger.Error(f"Client {client} is not the provider of service {service_name}")
            return
        del self._services[service_name]

    async def _subscribe(self,client,topic_name,type):
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

            # since the topic has no value yet, no update is sent to the client
        else:
            topic = self._topics[topic_name]

            # subscribe the client to the topic and send the current value to the client
            topic.AddSubscriber(client)
            await self._SendToClient(client,"update",topic_name=topic_name,change=ChangeSet(topic.Getvalue()).Serialize())

    #TODO async def _delete_topic(self,client,topic_name):

    async def _update(self,client,topic_name,change):
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
            if not response['valid']:
                await self._SendToClient(client,"reject_update",topic_name=topic_name,change=change,reason=response['reason'])
                return

        topic = self._topics[topic_name]
        topic.ApplyChange(change)

        # notify all subscribers
        await self._SendToClients(topic.GetSubscribers(),"update",topic_name=topic_name,change=change)

    async def _unsubscribe(self,client,topic_name):
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

    def MakeMessage(self,message_type,**kwargs)->str:
        return json.dumps({"type":message_type,"args":kwargs})

    def ParseMessage(self,message_json)->Tuple[str,dict]:
        message = json.loads(message_json)
        return message["type"],message["args"]
    
    async def _MakeRequest(self,service_name,**args):
        '''
        Send a request to a service provider and wait for the response
        '''
        provider = self._services[service_name].provider
        request_id = str(uuid.uuid4())
        await self._SendToClient(provider,"request",service_name=service_name,args=args,request_id=request_id)
        response = await self._evnt.Wait(f'response_waiter{request_id}')
        return response

    '''
    ================================
    Server functions
    ================================
    '''
    def Start(self):
        '''
        Bloking function that starts the server
        '''
        asyncio.set_event_loop(asyncio.new_event_loop())
        start_server = websockets.serve(self.HandleClient, "localhost", self._port)
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

    def __del__(self):
        print("Server deleted")
        self.Stop()


if __name__ == "__main__":
    chat_room = ChatroomServer()
    chat_room.Start()