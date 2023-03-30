from __future__ import annotations
from collections import deque
import contextlib
import copy
import json
import time
from typing import Any, Tuple, Type
from typing import Callable, List, Optional
from chatroom.state_machine.state_machine import StateMachine
from chatroom.topic_change import Change, InvalidChangeException, StringChangeTypes, SetChangeTypes, default_topic_value, typeValidator
from chatroom.utils import Action, camel_to_snake
import abc

def TopicFactory(topic_name:str,type:str,state_machine:StateMachine) -> Topic:
    if type == 'string':
        return StringTopic(topic_name,state_machine)
    if type == 'set':
        return SetTopic(topic_name,state_machine)
    raise ValueError(f'Unknown topic type {type}')

class Topic(metaclass = abc.ABCMeta):
    @classmethod
    def GetTypeName(cls):
        return camel_to_snake(cls.__name__.replace('Topic',''))
    
    def __init__(self,name,state_machine:StateMachine):
        self._name = name
        self._value = default_topic_value[self.GetTypeName()]
        self._validators : List[Callable[[Any,Any,Change],bool]] = []
        self._state_machine = state_machine
        self.subscribers = []
    
    def _ValidateChangeAndGetResult(self,change:Change):
        '''
        Validate the change and return the new value. Raise InvalidChangeException if the change is invalid.
        '''
        old_value = self._value
        try:
            new_value = change.Apply(copy.deepcopy(self._value))
        except InvalidChangeException as e:
            e.topic = self
            raise e
    
        for validator in self._validators:
            print(validator.__name__)
            if not validator(old_value,new_value,change):
                raise InvalidChangeException(self,change,f'Change {change.Serialize()} is not valid for topic {self._name}. Old value: {json.dumps(old_value)}, invalid new value: {json.dumps(new_value)}')
        
        return new_value

    '''
    API
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

    def ApplyChangeExternal(self, change:Change):
        '''
        Call this when the user or the app wants to change the value of the topic. The change is then be executed by the state machine.
        '''
        assert self._state_machine is not None
        command = self._state_machine.CreateChangeCommand(self.GetName(),change)
        self._state_machine.ApplyChange(command)        

    '''
    Called by the state machine
    '''

    def ApplyChange(self, change:Change, notify_listeners:bool = True):
        '''
        Set the value and notify listeners. 

        Note that only the state machine is allowed to call this method.
        '''
        old_value = self._value
        new_value = self._ValidateChangeAndGetResult(change)
        self._value = new_value
        if notify_listeners:
            self.NotifyListeners(change,old_value=old_value,new_value=self._value)
        return old_value,new_value

    @abc.abstractmethod
    def NotifyListeners(self,change:Change, old_value, new_value):
        '''
        Notify user-side listeners for a topic change. Every listener type work differently. Override this method in child classes to notify listeners of different types.
        
        Note that only a state machine or this topic are allowed to call this method.
        '''
        pass

class StringTopic(Topic):
    '''
    String topic
    '''
    def __init__(self,name,state_machine:StateMachine):
        super().__init__(name,state_machine)
        self.AddValidator(typeValidator(str))
        self.on_set = Action()
    
    def Set(self, value):
        change = StringChangeTypes.SetChange(value)
        self.ApplyChangeExternal(change)

    def NotifyListeners(self,change:Change, old_value, new_value):
        if isinstance(change,StringChangeTypes.SetChange):
            self.on_set(new_value)
        else:
            raise Exception(f'Unsupported change type {type(change)} for StringTopic')

class SetTopic(Topic):
    '''
    Unordered list topic
    '''
    
    def __init__(self,name,state_machine:StateMachine):
        super().__init__(name,state_machine)
        self.AddValidator(typeValidator(list))
        self.on_set = Action()
        self.on_append = Action()
        self.on_remove = Action()
    
    def Set(self, value):
        change = SetChangeTypes.SetChange(value)
        self.ApplyChangeExternal(change)

    def Append(self, item):
        change = SetChangeTypes.AppendChange(item)
        self.ApplyChangeExternal(change)

    def Remove(self, item):
        change = SetChangeTypes.RemoveChange(item)
        self.ApplyChangeExternal(change)        
    
    def __len__(self):
        return len(self._value)

    def NotifyListeners(self,change:Change, old_value:list, new_value:list):
        if isinstance(change,SetChangeTypes.SetChange):
            self.on_set(new_value)
            old_value_set = set(map(json.dumps,old_value))
            new_value_set = set(map(json.dumps,new_value))
            removed_items = old_value_set - new_value_set
            added_items = new_value_set - old_value_set
            for item in removed_items:
                self.on_remove(json.loads(item))
            for item in added_items:
                self.on_append(json.loads(item))

        elif isinstance(change,SetChangeTypes.AppendChange):
            self.on_set(new_value)
            self.on_append(change.item)
        elif isinstance(change,SetChangeTypes.RemoveChange):
            self.on_set(new_value)
            self.on_remove(change.item)
        else:
            raise Exception(f'Unsupported change type {type(change)} for SetTopic')