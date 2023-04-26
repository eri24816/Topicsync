from __future__ import annotations
import copy
import json
from typing import TYPE_CHECKING, Any, Callable, Generic, List, TypeVar
from chatroom.change import GenericChangeTypes, Change, IntChangeTypes, InvalidChangeError, StringChangeTypes, SetChangeTypes, FloatChangeTypes, default_topic_value, type_validator
from chatroom.utils import Action, camel_to_snake
import abc

if TYPE_CHECKING:
    from chatroom.state_machine import StateMachine

def topic_factory(topic_name:str,type:str,state_machine:StateMachine) -> Topic:
    '''
    Create a topic of the given type.
    '''
    if type == 'generic':
        return GenericTopic(topic_name,state_machine)
    if type == 'string':
        return StringTopic(topic_name,state_machine)
    if type == 'int':
        return IntTopic(topic_name,state_machine)
    if type == 'float':
        return FloatTopic(topic_name,state_machine)
    if type == 'set':
        return SetTopic(topic_name,state_machine)
    raise ValueError(f'Unknown topic type {type}')

class Topic(metaclass = abc.ABCMeta):
    @classmethod
    def get_type_name(cls):
        return camel_to_snake(cls.__name__.replace('Topic',''))
    
    def __init__(self,name,state_machine:StateMachine,is_stateful:bool = True):
        self._name = name
        self._value = default_topic_value[self.get_type_name()]
        self._validators : List[Callable[[Any,Any,Change],bool]] = []
        self._state_machine = state_machine
        self._is_stateful = is_stateful

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
        self.set(default_topic_value[self.get_type_name()])

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
    def __init__(self,name,state_machine:StateMachine):
        super().__init__(name,state_machine)
    
    def set(self, value:T):
        change = GenericChangeTypes.SetChange(self._name,value)
        self.apply_change_external(change)

class StringTopic(Topic):
    '''
    String topic
    '''
    def __init__(self,name,state_machine:StateMachine):
        super().__init__(name,state_machine)
        self.add_validator(type_validator(str))
        self.on_set = Action()
    
    def set(self, value):
        change = StringChangeTypes.SetChange(self._name,value)
        self.apply_change_external(change)
        
class IntTopic(Topic):
    '''
    Int topic
    '''
    def __init__(self,name,state_machine:StateMachine):
        super().__init__(name,state_machine)
        self.add_validator(type_validator(int))
        self.on_set = Action()
    
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
    def __init__(self,name,state_machine:StateMachine):
        super().__init__(name,state_machine)
        self.add_validator(type_validator(float,int))
        self.on_set = Action()
    
    def set(self, value:float):
        change = FloatChangeTypes.SetChange(self._name,value)
        self.apply_change_external(change)

    def add(self, value:float):
        change = FloatChangeTypes.AddChange(self._name,value)
        self.apply_change_external(change)

class SetTopic(Topic):
    '''
    Unordered list topic
    '''
    
    def __init__(self,name,state_machine:StateMachine):
        super().__init__(name,state_machine)
        self.add_validator(type_validator(list))
        self.on_set = Action()
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