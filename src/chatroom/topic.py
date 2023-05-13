from __future__ import annotations
import copy
import json
from typing import TYPE_CHECKING, Any, Callable, Generic, List, TypeVar
from chatroom.change import DictChangeTypes, EventChangeTypes, GenericChangeTypes, Change, IntChangeTypes, InvalidChangeError, StringChangeTypes, SetChangeTypes, FloatChangeTypes, default_topic_value, type_validator
from chatroom.logger import DEBUG, Logger
from chatroom.utils import Action, camel_to_snake
import abc

if TYPE_CHECKING:
    from chatroom.state_machine import StateMachine

def topic_factory(topic_type,name:str,state_machine:StateMachine,is_stateful:bool = True,init_value=None) -> Topic:
    '''
    Create a topic of the given type.
    '''
    return all_topic_types[topic_type](name,state_machine,is_stateful,init_value)

class Topic(metaclass = abc.ABCMeta):
    @classmethod
    def get_type_name(cls):
        return camel_to_snake(cls.__name__[:-5])
    
    def __init__(self,name,state_machine:StateMachine,is_stateful:bool = True,init_value=None):
        self._name = name
        self._validators : List[Callable[[Any,Any,Change],bool]] = []
        self._state_machine = state_machine
        self._is_stateful = is_stateful

        if init_value is not None:
            self._value = init_value
        else:
            self._value = copy.deepcopy(default_topic_value[self.get_type_name()])

        self.on_set = Action()
        """args:
        - value: the new value
        """

        self.on_set2 = Action()
        """args: 
        - before: the old value
        - after: the new value
        """
    
    def _validate_change_and_get_result(self,change:Change):
        '''
        Validate the change and return the new value. Raise InvalidChangeException if the change is invalid.
        '''
        old_value = self._value
        new_value = change.apply(copy.deepcopy(self._value))
    
        for validator in self._validators:
            if not validator(old_value,new_value,change):
                raise InvalidChangeError(change,'Validator failed') #TODO: Add more info
        
        return new_value

    '''
    API
    '''

    def get_name(self):
        return self._name
    
    def get(self):
        return copy.deepcopy(self._value)
    
    def add_validator(self,validator:Callable[[Any,Any,Change],bool]):
        '''
        Add a validator to the topic. The validator is a function that takes the old value, new value and the change as arguments and returns True if the change is valid and False otherwise.
        '''
        self._validators.append(validator)

    def apply_change_external(self, change:Change):
        '''
        Call this when the user or the app wants to change the value of the topic. The change is then be executed by the state machine.
        '''
        self._state_machine.apply_change(change)     

    def set_to_default(self):
        '''
        Set the topic to its default value.
        '''
        self.set(copy.deepcopy(default_topic_value[self.get_type_name()]))

    @abc.abstractmethod
    def set(self, value):
        '''
        Set the value of the topic.
        '''
        pass   

    '''
    Called by the state machine
    '''

    def apply_change(self, change:Change, notify_listeners:bool = True):
        '''
        Set the value and notify listeners. 

        Note that only the state machine is allowed to call this method.
        '''
        old_value = self._value
        new_value = self._validate_change_and_get_result(change)
        self._value = new_value

        Logger(DEBUG,'Topic').log(f'{self._name} changed from {old_value} to {new_value}',DEBUG)

        if notify_listeners:
            try:
                self.notify_listeners(change,old_value=old_value,new_value=self._value)
            except:
                self._value = old_value
                raise
        return old_value,new_value

    def notify_listeners(self,change:Change, old_value, new_value):
        '''
        Notify user-side listeners for a topic change. Every listener type work differently. Override this method in child classes to notify listeners of different types.
        
        Note that only a state machine or this topic are allowed to call this method.

        Override this method to notify listeners of different change types.
        '''
        self.on_set(new_value)
        self.on_set2(old_value, new_value)

    def is_stateful(self):
        return self._is_stateful

T = TypeVar('T')
class GenericTopic(Topic,Generic[T]):
    '''
    Topic of any/generic type (as long as it is JSON serializable)
    '''
    def __init__(self,name,state_machine:StateMachine,is_stateful:bool=True,init_value=None):
        super().__init__(name,state_machine,is_stateful,init_value)
    
    def set(self, value:T):
        change = GenericChangeTypes.SetChange(self._name,value)
        self.apply_change_external(change)

class StringTopic(Topic):
    '''
    String topic
    '''
    def __init__(self,name,state_machine:StateMachine,is_stateful:bool=True,init_value=None):
        super().__init__(name,state_machine,is_stateful,init_value)
        self.add_validator(type_validator(str))
    
    def set(self, value):
        change = StringChangeTypes.SetChange(self._name,value)
        self.apply_change_external(change)
        
class IntTopic(Topic):
    '''
    Int topic
    '''
    def __init__(self,name,state_machine:StateMachine,is_stateful:bool=True,init_value=None):
        super().__init__(name,state_machine,is_stateful,init_value)
        self.add_validator(type_validator(int))
    
    def set(self, value:int):
        change = IntChangeTypes.SetChange(self._name,value)
        self.apply_change_external(change)

    def add(self, value:int):
        change = IntChangeTypes.AddChange(self._name,value)
        self.apply_change_external(change)
        
class FloatTopic(Topic):
    '''
    Int topic
    '''
    def __init__(self,name,state_machine:StateMachine,is_stateful:bool=True,init_value=None):
        super().__init__(name,state_machine,is_stateful,init_value)
        
        self.add_validator(type_validator(float,int))
        self.on_set = Action()
    
    def set(self, value:float):
        change = FloatChangeTypes.SetChange(self._name,value)
        self.apply_change_external(change)

    def add(self, value:float):
        change = FloatChangeTypes.AddChange(self._name,value)
        self.apply_change_external(change)

class SetTopic(Topic):
    
    def __init__(self,name,state_machine:StateMachine,is_stateful:bool=True,init_value=None):
        super().__init__(name,state_machine,is_stateful,init_value)
        self.add_validator(type_validator(list))
        self.on_append = Action()
        self.on_remove = Action()
    
    def set(self, value):
        change = SetChangeTypes.SetChange(self._name,value)
        self.apply_change_external(change)

    def append(self, item):
        change = SetChangeTypes.AppendChange(self._name,item)
        self.apply_change_external(change)

    def remove(self, item):
        change = SetChangeTypes.RemoveChange(self._name,item)
        self.apply_change_external(change)        
    
    def __len__(self):
        return len(self._value)

    def notify_listeners(self,change:Change, old_value:list, new_value:list):
        super().notify_listeners(change,old_value,new_value)
        match change:
            case SetChangeTypes.SetChange():
                old_value_set = set(map(json.dumps,old_value))
                new_value_set = set(map(json.dumps,new_value))
                removed_items = old_value_set - new_value_set
                added_items = new_value_set - old_value_set
                for item in removed_items:
                    self.on_remove(json.loads(item))
                for item in added_items:
                    self.on_append(json.loads(item))
            case SetChangeTypes.AppendChange():
                self.on_append(change.item)
            case SetChangeTypes.RemoveChange():
                self.on_remove(change.item)
            case _:
                raise Exception(f'Unsupported change type {type(change)} for {self.__class__.__name__}')

class DictTopic(Topic):
    def __init__(self,name,state_machine:StateMachine,is_stateful:bool=True,init_value=None):
        super().__init__(name,state_machine,is_stateful,init_value)
        self.add_validator(type_validator(dict))
        self.on_set = Action()
        self.on_set2 = Action()
        self.on_add = Action()
        self.on_remove = Action()
        self.on_change_value = Action()
    
    def set(self, value):
        change = DictChangeTypes.SetChange(self._name,value)
        self.apply_change_external(change)

    def add(self, key, value):
        change = DictChangeTypes.AddChange(self._name,key,value)
        self.apply_change_external(change)

    def remove(self, key):
        change = DictChangeTypes.RemoveChange(self._name,key)
        self.apply_change_external(change)

    def change_value(self, key, value):
        change = DictChangeTypes.ChangeValueChange(self._name,key,value)
        self.apply_change_external(change)

    def __getitem__(self, key):
        return self._value[key]

    def notify_listeners(self,change:Change, old_value:dict, new_value:dict):
        super().notify_listeners(change,old_value,new_value)
        match change:
            case DictChangeTypes.SetChange():
                old_keys = set(old_value.keys())
                new_keys = set(new_value.keys())
                removed_keys = old_keys - new_keys
                added_keys = new_keys - old_keys
                remained_keys = old_keys & new_keys
                for key in removed_keys:
                    self.on_remove(key)
                for key in added_keys:
                    self.on_add(key,new_value[key])
                for key in remained_keys:
                    if old_value[key] != new_value[key]:
                        self.on_change_value(key,new_value[key])
            case DictChangeTypes.AddChange():
                self.on_add(change.key,change.value)
            case DictChangeTypes.RemoveChange():
                self.on_remove(change.key)
            case DictChangeTypes.ChangeValueChange():
                self.on_change_value(change.key,change.value)
            case _:
                raise Exception(f'Unsupported change type {type(change)} for {self.__class__.__name__}')
 
class EventTopic(Topic):
    '''
    Event topic
    '''
    def __init__(self,name,state_machine:StateMachine,is_stateful:bool=True,init_value=None):
        super().__init__(name,state_machine,is_stateful,init_value)
        self.on_emit = Action()
        self.on_reverse = Action()
    
    def set(self, value):
        raise NotImplementedError('You cannot set the value of an event topic.')

    def emit(self):
        change = EventChangeTypes.EmitChange(self._name)
        self.apply_change_external(change)

    def notify_listeners(self, change: Change, old_value, new_value):
        '''
        Not using super().notify_listeners() because we don't want to call on_set() and on_set2() for event topics.
        '''
        match change:
            case EventChangeTypes.EmitChange():
                forward_info = self.on_emit(**change.args)[0]
                if forward_info is None:
                    forward_info = {}
                change.forward_info = forward_info
            case EventChangeTypes.ReversedEmitChange():
                self.on_reverse(**change.args, **change.forward_info)
        
all_topic_types = {
    'generic': GenericTopic,
    'string': StringTopic,
    'int': IntTopic,
    'float': FloatTopic,
    'set': SetTopic,
    'dict': DictTopic,
    'event': EventTopic    
}