from __future__ import annotations
'''
Change is a class that represents a change to a topic. It can be serialized and be passed between clients and the server.
When the client wants to change a topic, it creates a Change object and sends it to the server. The server then applies the change to the topic (if it's valid).
The server then sends the change to all the subscribers of the topic.
'''
import random

class Change:
    @staticmethod
    def Deserialize(data):
        if data["type"] == "set":
            return ChangeSet(data["value"])
        raise Exception(f"Unknown change type {data['type']}")
    def __init__(self):
        self.id = random.randint(0,1000000000)
    def Apply(self, old_value):
        return old_value
    def Serialize(self):
        return {}
    def Inverse(self)->Change:
        '''
        Inverse() is defined after Apply called. It returns a change that will undo the change.
        '''
        return Change()
    
class ChangeSet(Change):
    def __init__(self, value):
        super().__init__()
        self.value = value
    def Apply(self, old_value):
        self.old_value = old_value
        return self.value
    def Serialize(self):
        return {"type":"set","value":self.value}
    def Inverse(self)->Change:
        return ChangeSet(self.old_value)
    
