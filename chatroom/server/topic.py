from typing import Dict


def CreateTopic(name,type,value):
    if type == 'string':
        return StringTopic(name,value)
    raise Exception(f"Unknown topic type {type}")

class Topic:
    def __init__(self,name,value):
        self._name = name
        self._value = value
        self._version = 0
        self._subscribers = set()

    def ApplyChange(self,change:Dict):
        if change['type'] == 'set':
            self._value = change['value']
            return True
        return False

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

class StringTopic(Topic):
    def __init__(self,name,value):
        super().__init__(name,value)

    def ApplyChange(self,change:Dict):
        if change['type'] == 'set':
            self._value = change['value']
            return True
        #TODO: add other change types
        return False