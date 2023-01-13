'''
In a chat room, every topic is synced across all clients.
Clients can subscribe to a topic and receive updates when the topic is updated.
Clients can also update a topic, which will be synced to all clients.
'''

from collections import defaultdict
import queue
import threading
from typing import Callable, Dict, List, Tuple
import websockets
import asyncio

from chatroom.server.event_manager import EventManager

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
        #self._request_pool : Dict[int,Request] = {}
        self._evnt = EventManager()
        self._pre_subscriptions : Dict[str,List[int]] = defaultdict(list) # subscriptions that are made before the topic is created
        
        self._message_handlers:Dict[str,Callable] = {}
        for message_type in ['request','response','register_service','unregister_service','try_update']:
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
            await self.SendToClient(client,"hello",id=client_id)
            #await self.Publish("_chatroom/server_status",f"[info] Client {client_id} connected")
            #await self.Publish(f"_chatroom/client_message/{client_id}",f"[info] Client {client_id} connected")

            async for message in client:
                self._logger.Debug(f"> {message}")
                message_type, content = self.ParseMessage(message)
                if message_type in self._message_handlers:
                    await self._message_handlers[message_type](client = client,**content)
                else:
                    self._logger.Error(f"Unknown message type: {message_type}")
                    pass
                    #await self.Publish(f"__client_message__/{client_id}",f"[error] Unknown message type: {message['type']}")
                # if message_type == "publish":
                #     await self.Publish(content["topic"],content["value"])
                # elif message_type == "subscribe":
                #     await self.Subscribe(client,content["topic"])
                # elif message_type == "unsubscribe":
                #     await self.Unsubscribe(client,content["topic"])
                # elif message_type == "try_publish":
                #     await self.TryPublish(client_id,content["topic"],content["change"])
                # elif message_type == "call":
                #     await self.Service(client,content["service"],content["command"],content["args"])
                # elif message_type == "response":
                #     await self.response(content["service"],content["data"])
                # else:
                #     await self.Publish(f"__client_message__/{client_id}",f"[error] Unknown message type: {message['type']}")
        except websockets.exceptions.ConnectionClosed as e:
            print(e)
            self._logger.Info(f"Client {client_id} disconnected")
            #await self.Publish("_chatroom/server_status",f"[info] Client {client_id} disconnected")
            # clear subscriptions
            for topic in self._topics.values():
                if client in topic.GetSubscribers():
                    topic.RemoveSubscriber(client)
            del self._clients[client_id]

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

    async def _request(self,client,service_name,args,request_id):
        '''
        Request a service. The server forwards the request to the service provider.
        '''
        # forward the request to the service provider, and wait for the response
        service = self._services[service_name]
        await self.SendToClient(service.provider,"request",service_name=service_name,args=args,request_id=request_id)
        response = await self._evnt.Wait(f'response_waiter{request_id}')
        
        # forward the response back to the client
        await self.SendToClient(client,"response",response=response,request_id=request_id)

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

    async def _create_topic(self,client,topic_name,type,value):
        '''
        Create a new topic
        '''
        # create the topic
        if topic_name in self._topics:
            self._logger.Error(f"Topic {topic_name} already exists")
            return
        topic = self._topics[topic_name] = CreateTopic(topic_name,type,value)

        # subscribe all pre-subscribers
        if topic_name in self._pre_subscriptions:
            for subscriber in self._pre_subscriptions.pop(topic_name):
                topic_name.AddSubscriber(subscriber)

        self._logger.Info(f"Created topic {topic_name} of type {type} with value {value}")

    async def _try_update(self,client,topic_name,change):
        '''
        Try to update a topic. The server first request the '_chatroom/validate_change' service to validate the change, then
        - forwards the update to all subscribers, if the change is valid
        - sends 'reject_update' message to the client, if the change is invalid
        If there is no '_chatroom/validate_change' service, the server will always accept the change.
        '''
        if topic_name not in self._topics:
            self._logger.Debug(f"Creating new topic {topic_name}.")
            self._topics[topic_name] = Topic(topic_name,change["value"])

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