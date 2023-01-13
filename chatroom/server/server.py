'''
In a chat room, every topic is synced across all clients.
Clients can subscribe to a topic and receive updates when the topic is updated.
Clients can also update a topic, which will be synced to all clients.
'''

import queue
import threading
from typing import Callable, Dict, Tuple
import websockets
import asyncio

from .topic import Topic
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
        self._request_pool : Dict[int,Request] = {}
        
        self._message_handlers:Dict[str,Callable] = {}
        for message_type in ['request','response','register_service','unregister_service']:
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
                # elif message_type == "respond":
                #     await self.Respond(content["service"],content["data"])
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
        
        print("Client disconnected aaa")

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
        service = self._services[service_name]
        self._request_pool.update({request_id:Request(request_id,client)})
        await self.SendToClient(service.provider,"request",service_name=service_name,args=args,request_id=request_id)

    async def _response(self,client,response,request_id):
        '''
        Response to a service request. The server forwards the response to the client.
        '''
        request = self._request_pool.pop(request_id)
        source_client = request.source_client
        await self.SendToClient(source_client,"response",response=response,request_id=request_id)

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