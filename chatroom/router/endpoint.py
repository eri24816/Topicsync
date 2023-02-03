import asyncio
from chatroom.utils import MakeMessage

class Endpoint:
    def __init__(self,id:int):
        self.id = id
    async def Send(self,*args,**kwargs):
        '''
        Send a message to the endpoint
        '''
        raise NotImplementedError

class WSEndpoint(Endpoint):
    def __init__(self,id,ws,logger):
        super().__init__(id)
        self._ws = ws
        self._logger = logger

    async def _SendRaw(self,message):
        await self._ws.send(message)
        self._logger.Debug(f"< {message}")

    async def Send(self,*args,**kwargs):
        await self._SendRaw(MakeMessage(*args,**kwargs))

class PythonEndpoint(Endpoint):
    def __init__(self,id,target):
        super().__init__(id)
        self._event_loop = None
        self._target = target
        self.queue_to_router = None

    def SetEventLoop(self,event_loop):
        self._event_loop = event_loop
        self.queue_to_router = asyncio.Queue(loop=event_loop)

    async def Send(self,message_type,*args,**kwargs):
        method = getattr(self._target,'_handle_'+message_type)
        method(*args,**kwargs)

    def SendToRouter(self,*args,**kwargs):
        assert isinstance(self._event_loop,asyncio.AbstractEventLoop)
        assert isinstance(self.queue_to_router,asyncio.Queue)
        self._event_loop.call_soon_threadsafe(self.queue_to_router.put_nowait,MakeMessage(*args,**kwargs))