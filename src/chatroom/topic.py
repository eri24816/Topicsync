from __future__ import annotations

import base64
from calendar import c
import collections
import copy
import json
import logging
logger = logging.getLogger(__name__)
from typing import TYPE_CHECKING, Any, Callable, Generic, Iterable, List, TypeVar, Dict
from chatroom.change import DictChangeTypes, EventChangeTypes, GenericChangeTypes, Change, IntChangeTypes, InvalidChangeError, ListChangeTypes, StringChangeTypes, SetChangeTypes, FloatChangeTypes, default_topic_value, type_validator
from chatroom.utils import Action, camel_to_snake
import abc

if TYPE_CHECKING:
    from chatroom.state_machine.state_machine import StateMachine

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
        self._validators : List[Callable[[Any,Change],bool]] = []
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
        new_value = change.apply(self._value)
    
        for validator in self._validators:
            if not validator(new_value,change):
                # If self._value is immutable, this line is not nessesary.
                # But if self._value is mutable, we need to revert the change.
                self._value = change.inverse().apply(new_value)
                raise InvalidChangeError(change,'Validator failed') #TODO: Add more info
        
        return new_value

    '''
    API
    '''

    def get_name(self):
        return self._name
    
    def get(self):
        return copy.deepcopy(self._value)

    def get_init_message(self):
        '''
        The message that is sent to a client in a 'init' command when it subscribes to the topic.
        In client, it is deserialized as a SetChange.
        '''
        return {"topic_name": self.get_name(), "value": self.get()}
    
    def add_validator(self,validator:Callable[[Any,Change],bool]):
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

    def apply_change(self, change:Change):
        '''
        Set the value and notify listeners. 

        Note that only the state machine is allowed to call this method.
        '''
        tmp = change.serialize()
        tmp.pop('topic_type')
        tmp.pop('topic_name')
        tmp.pop('id')
        printed = '\t'
        for s in [f'{k}:{v}' for k,v in tmp.items()]:
            printed += s
            printed += ', '
        
        logger.debug(f'{self._name} changed: {printed}')

        old_value = self._value
        new_value = self._validate_change_and_get_result(change)
        self._value = new_value
        return old_value,new_value

    def notify_listeners(self,auto:bool,change:Change, old_value, new_value):
        '''
        Notify user-side listeners for a topic change. Every listener type work differently. Override this method in child classes to notify listeners of different types.
        
        Note that only a state machine or this topic are allowed to call this method.

        Override this method to notify listeners of different change types.
        '''
        self.on_set.invoke(auto,new_value)
        self.on_set2.invoke(auto,old_value, new_value)

    def is_stateful(self):
        return self._is_stateful
    
    def merge_changes(self,changes:List[Change]):
        '''
        Merge consecutive changes to save network or computation resources. 
        Override this method in child classes to merge changes of different types.
        '''
        return changes

T = TypeVar('T')
class GenericTopic(Topic,Generic[T]):
    '''
    Topic of any/generic type (as long as it is JSON serializable)
    '''
    def __init__(self,name,state_machine:StateMachine,is_stateful:bool=True,init_value=None):
        super().__init__(name,state_machine,is_stateful,init_value)
    
    def set(self, value:T):
        if value == self._value:
            return
        change = GenericChangeTypes.SetChange(self._name,value)
        self.apply_change_external(change)

class StringTopic(Topic):
    '''
    String topic
    '''
    def __init__(self,name,state_machine:StateMachine,is_stateful:bool=True,init_value=None):
        super().__init__(name,state_machine,is_stateful,init_value)
        self.add_validator(type_validator(str))

        self.version = f"{name}_init"
        self.version_to_index: Dict[str, int] = {f"{name}_init": -1}
        self.changes: List[Change] = []

    def get_init_message(self):
        return super().get_init_message() | {'id': self.version} # client-side SetChange uses 'id' as version

    def _validate_change_and_get_result(self,change:Change):
        result_version = change.exchange_topic_version(self.version, self)
        result = super()._validate_change_and_get_result(change)
        self.version_to_index[result_version] = len(self.changes)
        self.changes.append(change)
        self.version = result_version
        return result

    def changes_from(self, version: str) -> Iterable[Change]:
        '''
        This method will throw if version isn't valid (isn't recorded by the topic)
        '''
        return self.changes[self.version_to_index[version] + 1:]
    
    def merge_changes(self,changes:List[Change]):
        stack: collections.deque[Change] = collections.deque()
        for change in changes:
            if isinstance(change, StringChangeTypes.SetChange):
                #  Overwrite all InsertChange or DeleteChange.
                while len(stack) and not isinstance(stack[-1], StringChangeTypes.SetChange):
                    stack.pop()
                if len(stack): # top is a SetChange
                    stack[-1].value = change.value # type: ignore # stack[-1] must be a SetChange
                    stack[-1].id = change.id
                    continue
                else: # stack is empty
                    stack.append(change)
                    continue
            else:
                stack.append(change)
                continue
            
        return stack
    
    def set(self, value):
        if value == self._value:
            return
        change = StringChangeTypes.SetChange(self._name,value)
        self.apply_change_external(change)

    def insert(self, position: int, insertion: str):
        change = StringChangeTypes.InsertChange(self._name, self.version, position, insertion)
        self.apply_change_external(change)

    def delete(self, position: int, deletion: str):
        change = StringChangeTypes.DeleteChange(self._name, self.version, position, deletion)
        self.apply_change_external(change)

    def set_from_binary(self, data):
        b64 = base64.b64encode(data).decode('utf-8')
        self.set(b64)

    def to_binary(self):
        return base64.b64decode(self._value)

        
class IntTopic(Topic):
    '''
    Int topic
    '''
    def __init__(self,name,state_machine:StateMachine,is_stateful:bool=True,init_value=None):
        super().__init__(name,state_machine,is_stateful,init_value)
        self.add_validator(type_validator(int))
    
    def set(self, value:int):
        if value == self._value:
            return
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
        if value == self._value:
            return
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
        if value == self._value:
            return
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
    
    def __iter__(self):
        return self._value.__iter__()
    
    def __contains__(self, item):
        return item in self._value

    def notify_listeners(self,auto:bool,change:Change, old_value:list, new_value:list):
        super().notify_listeners(auto,change,old_value,new_value)
        match change:
            case SetChangeTypes.SetChange():
                old_value_set = set(map(json.dumps,old_value))
                new_value_set = set(map(json.dumps,new_value))
                removed_items = old_value_set - new_value_set
                added_items = new_value_set - old_value_set
                for item in removed_items:
                    self.on_remove.invoke(auto,json.loads(item))
                for item in added_items:
                    self.on_append.invoke(auto,json.loads(item))
            case SetChangeTypes.AppendChange():
                self.on_append.invoke(auto,change.item)
            case SetChangeTypes.RemoveChange():
                self.on_remove.invoke(auto,change.item)
            case _:
                raise Exception(f'Unsupported change type {type(change)} for {self.__class__.__name__}')
            
class ListTopic(Topic):
    @staticmethod
    def unique_validator(new_value,change):
        '''
        Validator that prevents the list from having repeated items.
        '''
        return len(set(new_value)) == len(new_value)

    def __init__(self,name,state_machine:StateMachine,is_stateful:bool=True,init_value=None):
        super().__init__(name,state_machine,is_stateful,init_value)
        self.add_validator(type_validator(list))
        self.on_insert = Action()
        self.on_pop = Action()

    def merge_changes(self, changes: List[Change]):
        stack: collections.deque[Change] = collections.deque()
        for change in changes:
            if isinstance(change, ListChangeTypes.SetChange):
                #  Overwrite all InsertChange or DeleteChange.
                while len(stack) and not isinstance(stack[-1], ListChangeTypes.SetChange):
                    stack.pop()
                if len(stack):  # top is a SetChange
                    stack[-1].value = change.value  # type: ignore # stack[-1] must be a SetChange
                    stack[-1].id = change.id
                    continue
                else:  # stack is empty
                    stack.append(change)
                    continue
            else:
                stack.append(change)
                continue

        return stack
    
    def set(self, value):
        if value == self._value:
            return
        change = ListChangeTypes.SetChange(self._name,value)
        self.apply_change_external(change)
    
    def insert(self, item, position:int=-1):
        change = ListChangeTypes.InsertChange(self._name,item,position)
        self.apply_change_external(change)
    
    def pop(self, position:int=-1):
        change = ListChangeTypes.PopChange(self._name,position)
        self.apply_change_external(change)  

    def remove(self, item):
        position = self._value.index(item)
        change = ListChangeTypes.PopChange(self._name,position)
        self.apply_change_external(change)
    
    def __len__(self):
        return len(self._value)
    
    def __iter__(self):
        return self._value.__iter__()
    
    def __getitem__(self, key):
        return self._value[key]
    
    def __setitem__(self, position, value):
        self.pop(position)
        self.insert(value,position)

    def __delitem__(self, position):
        self.pop(position)
    
    def notify_listeners(self,auto:bool,change:Change, old_value:list, new_value:list):
        super().notify_listeners(auto,change,old_value,new_value)
        match change:
            case ListChangeTypes.SetChange():
                # pop all and insert all
                for i,item in reversed(list(enumerate(old_value))):
                    self.on_pop.invoke(auto,item,i)
                for i,item in enumerate(new_value):
                    self.on_insert.invoke(auto,item,i)
            case ListChangeTypes.InsertChange():
                self.on_insert.invoke(auto,change.item,change.position)
            case ListChangeTypes.PopChange():
                self.on_pop.invoke(auto,change.item,change.position)
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
        if value == self._value:
            return
        change = DictChangeTypes.SetChange(self._name,value)
        self.apply_change_external(change)

    def add(self, key, value):
        change = DictChangeTypes.AddChange(self._name,key,value)
        self.apply_change_external(change)

    def remove(self, value):
        self._value:Dict
        key = list(self._value.keys())[list(self._value.values()).index(value)]
        change = DictChangeTypes.PopChange(self._name,key)
        self.apply_change_external(change)

    def pop(self, key):
        temp = self._value[key]
        change = DictChangeTypes.PopChange(self._name,key)
        self.apply_change_external(change)
        return temp

    def change_value(self, key, value):
        change = DictChangeTypes.ChangeValueChange(self._name,key,value)
        self.apply_change_external(change)

    def __getitem__(self, key):
        return self._value[key]
    
    def __setitem__(self, key, value):
        self.add(key,value)
    
    def __delitem__(self, key):
        self.remove(key)

    def __contains__(self,key):
        return key in self._value

    def notify_listeners(self,auto:bool,change:Change, old_value:dict, new_value:dict):
        super().notify_listeners(auto,change,old_value,new_value)
        match change:
            case DictChangeTypes.SetChange():
                old_keys = set(old_value.keys())
                new_keys = set(new_value.keys())
                removed_keys = old_keys - new_keys
                added_keys = new_keys - old_keys
                remained_keys = old_keys & new_keys
                for key in removed_keys:
                    self.on_remove.invoke(auto,key)
                for key in added_keys:
                    self.on_add.invoke(auto,key,new_value[key])
                for key in remained_keys:
                    if old_value[key] != new_value[key]:
                        self.on_change_value.invoke(auto,key,new_value[key])
            case DictChangeTypes.AddChange():
                self.on_add.invoke(auto,change.key,change.value)
            case DictChangeTypes.PopChange():
                self.on_remove.invoke(auto,change.key)
            case DictChangeTypes.ChangeValueChange():
                self.on_change_value.invoke(auto,change.key,change.value)
            case _:
                raise Exception(f'Unsupported change type {type(change)} for {self.__class__.__name__}')
 
def merge_dicts(*dicts:dict):
    '''
    The order of the dicts is important. The last dict will override the previous ones.
    '''
    result = {}
    for d in dicts:
        result.update(d)
    return result

class EventTopic(Topic):
    '''
    Event topic
    '''
    def __init__(self,name,state_machine:StateMachine,is_stateful:bool=True,init_value=None):
        super().__init__(name,state_machine,is_stateful,init_value)
        self.on_emit = Action()
        self.on_reverse = Action()
    
    def set(self, value):
        return # do nothing

    def emit(self,args={}):
        change = EventChangeTypes.EmitChange(self._name,args)
        self.apply_change_external(change)

    def notify_listeners(self,auto:bool, change: Change, old_value, new_value):
        '''
        Not using super().notify_listeners(auto,) because we don't want to call on_set.invoke(auto,) and on_set2.invoke(auto,) for event topics.
        '''
        match change:
            case EventChangeTypes.EmitChange():
                args = merge_dicts(change.args,change.forward_info)
                forward_info_list = self.on_emit.invoke(auto,**args)
                if len(forward_info_list)>0 and forward_info_list[0] is not None:
                    if isinstance(forward_info_list[0],dict):
                        change.forward_info = forward_info_list[0]
                        
            case EventChangeTypes.ReversedEmitChange():
                args = merge_dicts(change.args,change.forward_info)
                self.on_reverse.invoke(auto,**args)

all_topic_types = {
    'generic': GenericTopic,
    'string': StringTopic,
    'int': IntTopic,
    'float': FloatTopic,
    'set': SetTopic,
    'dict': DictTopic,
    'list': ListTopic,
    'event': EventTopic
}