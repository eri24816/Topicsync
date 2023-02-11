from __future__ import annotations
from collections import deque
import contextlib
import copy
from typing import Any, Deque, Dict, Tuple, Type
from typing import Callable, List, TYPE_CHECKING, Optional
from itertools import count
from chatroom.command import ChangeCommand
if TYPE_CHECKING:
    from .client.client import ChatroomClient
    from .command import CommandManager
from chatroom.topic_change import Change, InvalidChangeException, StringChangeTypes, UListChangeTypes, default_topic_value
from chatroom.utils import Action, camel_to_snake
import abc

def TopicFactory(topic_name:str,type:str,get_topic_by_name:Optional[Callable[[str],Topic]]=None,command_manager:Optional[CommandManager]=None) -> Topic:
    if type == 'string':
        return StringTopic(topic_name,get_topic_by_name,command_manager)
    if type == 'u_list':
        return UListTopic(topic_name,get_topic_by_name,command_manager)
    raise ValueError(f'Unknown topic type {type}')

class Topic(metaclass = abc.ABCMeta):
    @classmethod
    def GetTypeName(cls):
        return camel_to_snake(cls.__name__.replace('Topic',''))
    
    def __init__(self,name,get_topic_by_name:Optional[Callable[[str],Topic]]=None,command_manager:Optional[CommandManager]=None):
        self._name = name
        self._value = default_topic_value[self.GetTypeName()]
        self._validators : List[Callable[[Any,Any,Change],bool]] = []
        self._get_topic_by_name = get_topic_by_name
        self._command_manager = command_manager
        self._no_preview_change_types : List[Type[Change]] = []
        self.subscribers = []

    def __del__(self):
        #TODO unsubscribe if here is client
        pass
        
    '''
    User-side methods
    '''

    def GetName(self):
        return self._name
    
    def GetValue(self):
        return copy.deepcopy(self._value)
    
    def AddValidator(self,validator:Callable[[Any,Any,Change],bool]):
        '''
        Add a validator to the topic. The validator is a function that takes the old value, new value and the change as arguments and returns True if the change is valid and False otherwise.
        '''
        self._validators.append(validator)

    def DisablePreview(self,change_type:Optional[Type[Change]]):
        if change_type is None:
            self._no_preview_change_types = list(Change.__subclasses__())
        else:
            self._no_preview_change_types.append(change_type)

    def EnablePreview(self,change_type:Optional[Type[Change]]):
        if change_type is None:
            self._no_preview_change_types = []
        else:
            self._no_preview_change_types.remove(change_type)
        
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

    def SetChildrenList(self,children_list:UListTopic):
        self._children_list = children_list

    def ValidateChangeAndGetResult(self,change:Change):
        old_value = self._value
        new_value = change.Apply(copy.deepcopy(self._value))

        for validator in self._validators:
            if not validator(old_value,new_value,change):
                raise InvalidChangeException(f'Change {change.Serialize()} is not valid for topic {self._name}. Old value: {old_value}, invalid new value: {new_value}')
        
        return new_value

    def ApplyChange(self, change:Change):
        '''
        Set the value and notify listeners. Note that this method does not record the change in the command manager. Use ApplyChangeExternal instead.
        '''
        old_value = self._value
        new_value = self.ValidateChangeAndGetResult(change)
        self._value = new_value
        self._NotifyListeners(change,old_value=old_value,new_value=self._value)

    def ApplyChangeExternal(self, change:Change):
        '''
        Call this when the user or the app wants to change the value of the topic. The change is recorded in the command manager (then can be sent to the router).
        '''
        if self._command_manager is None:
            self.ApplyChange(change)
            return

        self.ValidateChangeAndGetResult(change)
        
        preview = type(change) not in self._no_preview_change_types # this value is only used in the client
        assert self._get_topic_by_name is not None
        with self._command_manager.Record(allow_already_recording=True):
            self._command_manager.Add(ChangeCommand(self._get_topic_by_name,self._name,change,preview=preview))

    '''
    Shortcuts
    '''
    def DeserializeChange(self, change_dict):
        return Change.Deserialize(self.GetTypeName(),change_dict)   

class StringTopic(Topic):
    '''
    String topic
    '''
    def __init__(self,name,get_topic_by_name=None,command_manager:Optional[CommandManager]=None):
        super().__init__(name,get_topic_by_name,command_manager)
        self.on_set = Action()
    
    def Set(self, value):
        change = StringChangeTypes.SetChange(value)
        self.ApplyChangeExternal(change)

    def _NotifyListeners(self,change:Change, old_value, new_value):
        if isinstance(change,StringChangeTypes.SetChange):
            self.on_set(new_value)
        else:
            raise Exception(f'Unsupported change type {type(change)} for StringTopic')

class UListTopic(Topic):
    '''
    Unordered list topic
    '''
    @staticmethod
    def NoRepeatsValidator(old_value,new_value,change):
        if isinstance(change,UListChangeTypes.AppendChange):
            if change.item in old_value:
                return False
        elif isinstance(change,UListChangeTypes.SetChange):
            if len(change.value) != len(set(change.value)):
                return False
        return True
    
    def __init__(self,name,get_topic_by_name=None,command_manager:Optional[CommandManager]=None):
        super().__init__(name,get_topic_by_name,command_manager)
        self.on_set = Action()
        self.on_append = Action()
        self.on_remove = Action()
    
    def Set(self, value):
        change = UListChangeTypes.SetChange(value)
        self.ApplyChangeExternal(change)

    def Append(self, item):
        change = UListChangeTypes.AppendChange(item)
        self.ApplyChangeExternal(change)

    def Remove(self, item):
        change = UListChangeTypes.RemoveChange(item)
        self.ApplyChangeExternal(change)        

    def __getitem__(self, index):
        return copy.deepcopy(self._value[index])
    
    def __len__(self):
        return len(self._value)

    def _NotifyListeners(self,change:Change, old_value, new_value):
        if isinstance(change,UListChangeTypes.SetChange):
            self.on_set(new_value)
            
            removed_items = copy.deepcopy(old_value)
            added_items = copy.deepcopy(new_value)
            
            for item in removed_items:
                if item in added_items:
                    added_items.remove(item)
                    removed_items.remove(item)
            for item in removed_items:
                self.on_remove(item)
            for item in added_items:
                self.on_append(item)

        elif isinstance(change,UListChangeTypes.AppendChange):
            self.on_set(new_value)
            self.on_append(change.item)
        elif isinstance(change,UListChangeTypes.RemoveChange):
            self.on_set(new_value)
            self.on_remove(change.item)
        else:
            raise Exception(f'Unsupported change type {type(change)} for UListTopic')