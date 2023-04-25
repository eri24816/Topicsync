from __future__ import annotations
from typing import TYPE_CHECKING, Any, Optional
import copy

if TYPE_CHECKING:
    from chatroom.topic import Topic
'''
Change is a class that represents a change to a topic. It can be serialized and be passed between clients and the server.
When the client wants to change a topic, it creates a Change object and sends it to the server. The server then applies the change to the topic (if it's valid).
The server then sends the change to all the subscribers of the topic.
'''
import uuid

class InvalidChangeError(Exception):
    def __init__(self,change:Change,reason:str):
        super().__init__(f'Invalid {change.__class__.__name__} for topic {change.topic_name}: {reason} Change: {change.serialize()}')
        self.change = change
        self.reason = reason

default_topic_value = {
    'generic':None,
    'string':'',
    'int':0,
    'float':0.0,
    'bool':False,
    'set':[],
    'list':[],
}

def remove_entry(dictionary,key):
    dictionary = dictionary.copy()
    if key in dictionary:
        del dictionary[key]
    return dictionary

def type_validator(*ts):
    def f(old_value,new_value,change):
        for t in ts:
            if isinstance(new_value,t):
                return True
        return False
    return f

class Change: 
    @staticmethod
    def deserialize(change_dict:dict[str,Any])->Change:
        change_type, topic_type, change_dict = change_dict['type'], change_dict['topic_type'], remove_entry(remove_entry(change_dict,'type'),'topic_type')
        return type_name_to_change_types[topic_type].types[change_type](**change_dict)
    
    def __init__(self,topic_name,id:Optional[str]=None):
        self.topic_name = topic_name
        if id is None:
            self.id = str(uuid.uuid4())
        else:
            self.id = id
    def apply(self, old_value):
        return old_value
    def serialize(self):
        raise NotImplementedError()
    def inverse(self)->Change:
        '''
        Inverse() is defined after Apply called. It returns a change that will undo the change.
        '''
        return Change(self.topic_name)

class SetChange(Change):
    def __init__(self,topic_name, value,old_value=None,id=None):
        super().__init__(topic_name,id)
        assert value != [5]
        self.value = value
        self.old_value = old_value
    def apply(self, old_value):
        if self.old_value != old_value:
            # If the old value is different, then this change is not the same as the one that was sent to the server.
            self.id = str(uuid.uuid4()) 
        self.old_value = old_value
        return copy.deepcopy(self.value)
    def inverse(self)->Change:
        return self.__class__(self.topic_name,copy.deepcopy(self.old_value),copy.deepcopy(self.value))
    def serialize(self):
        return {"topic_name":self.topic_name,"topic_type":"unknown","type":"set","value":self.value,"old_value":self.old_value,"id":self.id}

class GenericChangeTypes:
    class SetChange(SetChange):
        def serialize(self):
            return {"topic_name":self.topic_name,"topic_type":"generic","type":"set","value":self.value,"old_value":self.old_value,"id":self.id}
        
    types = {'set':SetChange}

class StringChangeTypes:
    class SetChange(SetChange):
        def serialize(self):
            return {"topic_name":self.topic_name,"topic_type":"string","type":"set","value":self.value,"old_value":self.old_value,"id":self.id}
        
    types = {'set':SetChange}

class IntChangeTypes:
    class SetChange(SetChange):
        def serialize(self):
            return {"topic_name":self.topic_name,"topic_type":"int","type":"set","value":self.value,"old_value":self.old_value,"id":self.id}
    
    class AddChange(Change):
        def __init__(self,topic_name, value,id=None):
            super().__init__(topic_name,id)
            self.value = value
        def apply(self, old_value):
            return old_value + self.value
        def serialize(self):
            return {"topic_name":self.topic_name,"topic_type":"int","type":"add","value":self.value,"id":self.id}
        def inverse(self)->Change:
            return IntChangeTypes.AddChange(self.topic_name,-self.value)
    
    types = {'set':SetChange,'add':AddChange}

class FloatChangeTypes:
    class SetChange(SetChange):
        def serialize(self):
            return {"topic_name":self.topic_name,"topic_type":"float","type":"set","value":self.value,"old_value":self.old_value,"id":self.id}
    
    class AddChange(Change):
        def __init__(self,topic_name, value,id=None):
            super().__init__(topic_name,id)
            self.value = value
        def apply(self, old_value):
            return old_value + self.value
        def serialize(self):
            return {"topic_name":self.topic_name,"topic_type":"float","type":"add","value":self.value,"id":self.id}
        def inverse(self)->Change:
            return IntChangeTypes.AddChange(self.topic_name,-self.value)
    
    types = {'set':SetChange,'add':AddChange}

class SetChangeTypes:
    class SetChange(SetChange):
        def serialize(self):
                return {"topic_name":self.topic_name,"topic_type":"set","type":"set","value":self.value,"old_value":self.old_value,"id":self.id}
    class AppendChange(Change):
        def __init__(self,topic_name, item,id=None):
            super().__init__(topic_name,id)
            self.item = item
        def apply(self, old_value):
            if self.item in old_value:
                raise InvalidChangeError(self,f'Adding {repr(self.item)} to {old_value} would create a duplicate.')
            return old_value + [self.item]
        def serialize(self):
            return {"topic_name":self.topic_name,"topic_type":"set","type":"append","item":self.item,"id":self.id}
        def inverse(self)->Change:
            return SetChangeTypes.RemoveChange(self.topic_name,self.item)
        
    class RemoveChange(Change):
        def __init__(self,topic_name, item,id=None):
            super().__init__(topic_name,id)
            self.item = item
        def apply(self, old_value):
            if self.item not in old_value:
                raise InvalidChangeError(self,f'Cannot remove {self.item} from {old_value}')
            new_value = old_value[:]
            new_value.remove(self.item)
            return new_value
        def serialize(self):
            return {"topic_name":self.topic_name,"topic_type":"set","type":"remove","item":self.item,"id":self.id}
        def inverse(self)->Change:
            return SetChangeTypes.AppendChange(self.topic_name,self.item)
    
    types = {'set':SetChange,'append':AppendChange,'remove':RemoveChange}

type_name_to_change_types = {
                                'generic':GenericChangeTypes,
                                'string':StringChangeTypes,
                                'int':IntChangeTypes,
                                'float':FloatChangeTypes,
                                'set':SetChangeTypes
                            }