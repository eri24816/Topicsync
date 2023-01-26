from chatroom.topic_change import Change, InvalidChangeException
from chatroom.utils import camel_to_snake
import copy
import abc

class Topic(metaclass = abc.ABCMeta):
    def __init__(self,server,name) -> None:
        self._server = server
        self._name = name
        self._value = None
    
    '''
    User-side methods
    '''
    
    def GetName(self):
        return self._name
    
    def GetTypeName(self):
        return camel_to_snake(self.__class__.__name__.replace('Topic',''))
    
    def GetValue(self):
        return copy.deepcopy(self._value)
    
    def ApplyChange(self,change):
        '''
        Apply a change to the topic. If the change is invalid, an InvalidChangeException will be raised.
        '''
        self._value = change.Apply(self._value)
    
    '''
    Private methods
    '''
    @abc.abstractmethod
    def _NotifyListeners(self,change:Change, old_value, new_value):
        # notify user-side listeners for a topic change. Every listener type work differently. Override this method in child classes to notify listeners of different types.
        pass

class StringTopic(Topic):
    def __init__(self,server,name,value) -> None:
        super().__init__(server,name)
        self._value = value