from __future__ import annotations
'''
Change is a class that represents a change to a topic. It can be serialized and be passed between clients and the server.
When the client wants to change a topic, it creates a Change object and sends it to the server. The server then applies the change to the topic (if it's valid).
The server then sends the change to all the subscribers of the topic.
'''
import uuid

def remove_entry(dictionary,key):
    dictionary = dictionary.copy()
    if key in dictionary:
        del dictionary[key]
    return dictionary

class Change:
    @staticmethod
    def Deserialize(data):
        if data["type"] == "set":
            return SetChange(**remove_entry(data,'type'))
        raise Exception(f"Unknown change type {data['type']}")
    def __init__(self,id=None):
        if id is None:
            self.id = str(uuid.uuid4())
        else:
            self.id = id
    def Apply(self, old_value):
        return old_value
    def Serialize(self):
        return {}
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
        return SetChange(self.old_value,self.value)
    
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
    def Inverse(self)->Change:
        return RemoveChange(self.item)
    
class RemoveChange(Change):
    '''
    Remove a value from a list. Apply() will remove the value from the list inplace and return the list.
    '''
    def __init__(self, item,id=None):
        super().__init__(id)
        self.item = item
    def Apply(self, old_value):
        old_value.remove(self.item)
        return old_value
    def Inverse(self)->Change:
        return AppendChange(self.item)
