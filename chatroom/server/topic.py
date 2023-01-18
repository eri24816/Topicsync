from typing import Dict
from chatroom.topic_change import Change, DeserializeChange

default_topic_value = {
    'string':'',
    'int':0,
    'float':0.0,
    'bool':False,
    'list':[],
}

def CreateTopic(name,type:str,value=None):
    if value is None:
        value = default_topic_value[type]
    return Topic(name,value,type)

class Topic:
    '''
    The topic class at server side code.
    '''
    def __init__(self,name,value,type):
        self._name = name
        self._value = value
        self._version = 0
        self._subscribers = set()
        self._type = type

    def ApplyChange(self,change_dict:Dict):
        change = DeserializeChange(self._type,change_dict)
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
