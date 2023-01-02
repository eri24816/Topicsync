class Service:
    def __init__(self,name) -> None:
        self._name = name
        self._provider = None

    def GetName(self):
        return self._name

    def SetProvider(self,provider):
        self._provider = provider

    async def Request(self,source,data):
        awa

    async def Respond(self,data):
        pass