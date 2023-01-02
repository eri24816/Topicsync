class Topic:
    def __init__(self,name,value):
        self._name = name
        self._value = value
        self._version = 0
        self._subscribers = set()

    def Update(self,value):
        self._value = value
        self._version += 1

    def AddSubscriber(self,subscriber):
        self._subscribers.add(subscriber)

    def RemoveSubscriber(self,subscriber):
        self._subscribers.remove(subscriber)

    def Getvalue(self):
        return self._value

    def GetVersion(self):
        return self._version

    def GetSubscribers(self):
        return self._subscribers

