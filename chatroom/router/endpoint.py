from chatroom.utils import MakeMessage

class Endpoint:
    async def Send(self,*args,**kwargs):
        '''
        Send a message to the endpoint
        '''
        raise NotImplementedError

class WSEndpoint(Endpoint):
    def __init__(self,ws,logger):
        self._ws = ws
        self._logger = logger

    async def _SendRaw(self,message):
        await self._ws.send(message)
        self._logger.Debug(f"< {message}")

    async def Send(self,*args,**kwargs):
        await self._SendRaw(MakeMessage(*args,**kwargs))

class PythonEndpoint(Endpoint):
    def __init__(self,target):
        self._target = target

    async def Send(self,message_type,*args,**kwargs):
        method = getattr(self._target,message_type)
        method(*args,**kwargs)