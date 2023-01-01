class Topic:
    def __init__(self,name,payload):
        self._name = name
        self._payload = payload
        self._version = 0
        self._subscribers = []

    def Update(self,payload):
        self._payload = payload
        self._version += 1

    def AddSubscriber(self,subscriber):
        self._subscribers.append(subscriber)

    def RemoveSubscriber(self,subscriber):
        self._subscribers.remove(subscriber)

    def GetPayload(self):
        return self._payload

    def GetVersion(self):
        return self._version

    def GetSubscribers(self):
        return self._subscribers

