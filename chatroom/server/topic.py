from typing import Dict
from chatroom.topic_change import Change

def GuessType(value):
    if isinstance(value,str):
        return 'string'
    return 'string'

default_topic_value = {
    'string':'',
    'int':0,
    'float':0.0,
    'bool':False,
    'list':[],
}

def CreateTopic(name,type=None,value=None):
    if value is None:
        if type is None:
            type = GuessType(value)
        value = default_topic_value[type]
    return Topic(name,value)

class Topic:
    def __init__(self,name,value):
        self._name = name
        self._value = value
        self._version = 0
        self._subscribers = set()

    def ApplyChange(self,change_dict:Dict):
        change = Change.Deserialize(change_dict)
        self._value = change.Apply(self._value)

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
