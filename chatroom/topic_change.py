from __future__ import annotations
'''
Change is a class that represents a change to a topic. It can be serialized and be passed between clients and the server.
When the client wants to change a topic, it creates a Change object and sends it to the server. The server then applies the change to the topic (if it's valid).
The server then sends the change to all the subscribers of the topic.
'''
import uuid

class InvalidChangeError(Exception):
    pass

default_topic_value = {
    'string':'',
    'int':0,
    'float':0.0,
    'bool':False,
    'u_list':[],
    'list':[],
}

def remove_entry(dictionary,key):
    dictionary = dictionary.copy()
    if key in dictionary:
        del dictionary[key]
    return dictionary

def DeserializeChange(topic_type, change_dict)->Change:
    change_type, change_dict = change_dict['type'], remove_entry(change_dict,'type')
    return TypeNameToChangeTypes[topic_type].types[change_type](**change_dict)

class Change: 
    def __init__(self,id=None):
        if id is None:
            self.id = str(uuid.uuid4())
        else:
            self.id = id
    def Apply(self, old_value):
        return old_value
    def Serialize(self):
        raise NotImplementedError()
    def Inverse(self)->Change:
        '''
        Inverse() is defined after Apply called. It returns a change that will undo the change.
        '''
        return Change()

class SetChange(Change):
    def __init__(self, value,old_value=None,id=None):
        super().__init__(id)
        self.value = value
        self.old_value = old_value
    def Apply(self, old_value):
        self.old_value = old_value
        return self.value
    def Serialize(self):
        return {"type":"set","value":self.value,"old_value":self.old_value,"id":self.id}
    def Inverse(self)->Change:
        return self.__class__(self.old_value,self.value)

class StringChangeTypes:
    class SetChange(SetChange):
        pass
    
    types = {'set':SetChange}

class UListChangeTypes:
    class SetChange(SetChange):
        pass
    class AppendChange(Change):
        '''
        Append a value to a list. Apply() will append the value to the list inplace and return the list.
        '''
        def __init__(self, item,id=None):
            super().__init__(id)
            self.item = item
        def Apply(self, old_value):
            old_value.append(self.item)
            return old_value
        def Serialize(self):
            return {"type":"append","item":self.item,"id":self.id}
        def Inverse(self)->Change:
            return UListChangeTypes.RemoveChange(self.item)
        
    class RemoveChange(Change):
        '''
        Remove a value from a list. Apply() will remove the value from the list inplace and return the list.
        '''
        def __init__(self, item,id=None):
            super().__init__(id)
            self.item = item
        def Apply(self, old_value):
            if self.item not in old_value:
                raise InvalidChangeError(f'{self.item} is not in {old_value}')
            old_value.remove(self.item)
            return old_value
        def Serialize(self):
            return {"type":"remove","item":self.item,"id":self.id}
        def Inverse(self)->Change:
            return UListChangeTypes.AppendChange(self.item)
    
    types = {'set':SetChange,'append':AppendChange,'remove':RemoveChange}

TypeNameToChangeTypes = {'string':StringChangeTypes,'u_list':UListChangeTypes}