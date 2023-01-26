from __future__ import annotations
from collections import deque
import contextlib
import copy
from typing import Deque, Dict, Tuple
from typing import Callable, List, TYPE_CHECKING, Optional
from itertools import count
if TYPE_CHECKING:
    from .client.client import ChatroomClient
    from .command import CommandManager
from chatroom.topic_change import Change, StringChangeTypes, UListChangeTypes, default_topic_value
from chatroom.utils import Action, camel_to_snake
import abc

class Topic(metaclass = abc.ABCMeta):

    def __init__(self,name,client:ChatroomClient,command_manager:Optional[CommandManager]=None):
        self.client = client
        self._name = name
        self._value = default_topic_value[self.GetTypeName()]
        self._command_manager = command_manager

    def __del__(self):
        self.client.Unsubscribe(self._name)
        
    '''
    User-side methods
    '''

    def GetName(self):
        return self._name
    
    def GetTypeName(self):
        return camel_to_snake(self.__class__.__name__.replace('Topic',''))
    
    def GetValue(self):
        return copy.deepcopy(self._value)
        
    '''
    Abstract/virtual methods
    '''

    @abc.abstractmethod
    def _NotifyListeners(self,change:Change, old_value, new_value):
        # notify user-side listeners for a topic change. Every listener type work differently. Override this method in child classes to notify listeners of different types.
        pass

    '''
    Public methods
    '''

    def ApplyChange(self, change:Change):
        '''
        Set the display value and notify listeners. Note that this method does not send the change to the server.
        '''
        old_value = self._value
        self._value = change.Apply(self._value)
        self._NotifyListeners(change,old_value=old_value,new_value=self._value)

    def UpdateByUser(self, change:Change):
        '''
        Call this when the user want to change the value of the topic. The change is recorded in the command manager (then sent to the router).
        '''
        context = self._command_manager.Record(allow_already_recording=True) if self._command_manager is not None else contextlib.nullcontext()
        with context:
            self.ApplyChange(change)

    '''
    Shortcuts
    '''
    def DeserializeChange(self, change_dict):
        return Change.Deserialize(self.GetTypeName(),change_dict)   

class StringTopic(Topic):
    '''
    String topic
    '''
    def __init__(self,name,client:ChatroomClient):
        super().__init__(name,client)
        self.on_set = Action()
    
    def Set(self, value):
        change = StringChangeTypes.SetChange(value)
        self.UpdateByUser(change)

    def _NotifyListeners(self,change:Change, old_value, new_value):
        if isinstance(change,StringChangeTypes.SetChange):
            self.on_set(new_value)
        else:
            raise Exception(f'Unsupported change type {type(change)} for StringTopic')

class UListTopic(Topic):
    '''
    Unordered list topic
    '''
    def __init__(self,name,client:ChatroomClient):
        super().__init__(name,client)
        self.on_set = Action()
        self.on_append = Action()
        self.on_remove = Action()
    
    def Set(self, value):
        change = UListChangeTypes.SetChange(value)
        self.UpdateByUser(change)

    def Append(self, item):
        change = UListChangeTypes.AppendChange(item)
        self.UpdateByUser(change)

    def Remove(self, item):
        change = UListChangeTypes.RemoveChange(item)
        self.UpdateByUser(change)        

    def __getitem__(self, index):
        return copy.deepcopy(self._value[index])
    
    def __len__(self):
        return len(self._value)

    def _NotifyListeners(self,change:Change, old_value, new_value):
        if isinstance(change,UListChangeTypes.SetChange):
            self.on_set(new_value)
            for item in old_value:
                self.on_remove(item)
            for item in new_value:
                self.on_append(item)
        elif isinstance(change,UListChangeTypes.AppendChange):
            self.on_set(new_value)
            self.on_append(change.item)
        elif isinstance(change,UListChangeTypes.RemoveChange):
            self.on_set(new_value)
            self.on_remove(change.item)
        else:
            raise Exception(f'Unsupported change type {type(change)} for UListTopic')