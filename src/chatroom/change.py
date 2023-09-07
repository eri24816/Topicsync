from __future__ import annotations
from typing import TYPE_CHECKING, Any, List, Optional, Self
import copy

from chatroom.utils import IdGenerator
from chatroom.string_diff import insert, delete, adjust_delete, extend_delete

if TYPE_CHECKING:
    from chatroom.topic import Topic, StringTopic
'''
Change is a class that represents a change to a topic. It can be serialized and be passed between clients and the server.
When the client wants to change a topic, it creates a Change object and sends it to the server. The server then applies the change to the topic (if it's valid).
The server then sends the change to all the subscribers of the topic.
'''

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
    'dict':{},
    'event':None
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
        return type_name_to_change_types[topic_type].types[change_type].deserialize_init(change_dict)

    @classmethod
    def deserialize_init(cls, change_dict: dict[str, Any]) -> Self:
        return cls(**change_dict)

    def __init__(self,topic_name,id:Optional[str]=None):
        self.topic_name = topic_name
        if id is None:
            self.id = IdGenerator.generate_id()
        else:
            self.id = id
    def apply(self, old_value):
        return old_value
    def serialize(self)->dict[str,Any]:
        raise NotImplementedError()
    def inverse(self)->Change:
        '''
        Inverse() is defined after Apply called. It returns a change that will undo the change.
        '''
        raise NotImplementedError()

class NullChange(Change):
    def __init__(self,topic_name,id=None):
        super().__init__(topic_name,id)
    def apply(self, old_value):
        return old_value
    def inverse(self)->Change:
        return self
    def serialize(self):
        raise NotImplementedError('NullChange should be discarded before serialization.')

class SetChange(Change):
    def __init__(self,topic_name, value,old_value=None,id=None):
        super().__init__(topic_name,id)
        self.value = copy.deepcopy(value)
        self.old_value = copy.deepcopy(old_value)
    def apply(self, old_value):
        old_value = copy.deepcopy(old_value)
        # if self.old_value != None:
        #     #? Is it correct?
        #     assert old_value == self.old_value, f'old_value: {old_value} != self.old_value: {self.old_value}'
        if self.old_value != old_value:
            # If the old value is different, then this change is not the same as the one that was sent to the server.
            self.id = IdGenerator.generate_id()
        self.old_value = old_value
        return copy.deepcopy(self.value)
    def inverse(self)->Change:
        return self.__class__(self.topic_name,copy.deepcopy(self.old_value),copy.deepcopy(self.value))
    def serialize(self):
        return {"topic_name":self.topic_name,"topic_type":"unknown","type":"set","value":self.value,"old_value":self.old_value,"id":self.id}
    def __eq__(self, other):
        if type(self) != type(other):
            # type will return the immediate type (simply, subtype), so we use type and compare them directly
            # simple subclass of SetChange therefore don't need to write their own __eq__ method
            return False
        return self.topic_name == other.topic_name and \
            self.value == other.value and \
            self.old_value == other.old_value and \
            self.id == other.id


class GenericChangeTypes:
    class SetChange(SetChange):
        def serialize(self):
            return {"topic_name":self.topic_name,"topic_type":"generic","type":"set","value":self.value,"old_value":self.old_value,"id":self.id}

    types = {'set':SetChange}

class StringChangeTypes:
    class SetChange(SetChange):
        def sync_topic_version(self, current_version: str, topic: StringTopic):
            pass
        def serialize(self):
            return {"topic_name":self.topic_name,"topic_type":"string","type":"set","value":self.value,"old_value":self.old_value,"id":self.id}

    class InsertChange(Change):
        def __init__(self, topic_name: str, topic_version: str, position: int, insertion: str, id: Optional[str]=None):
            super().__init__(topic_name, id)
            self.position = position
            self.insertion = insertion
            self.topic_version = topic_version

        def sync_topic_version(self, current_version: str, topic: StringTopic):
            if self.topic_version == current_version:
                return

            try:
                changes = topic.changes_from(self.topic_version)
            except:
                raise InvalidChangeError(self, f"Invalid base topic version: {self.topic_version}")

            for change in changes:
                if isinstance(change, StringChangeTypes.SetChange):
                    # view it as delete all and insert all, the cursor should be at the beginning
                    self.position = 0
                else:
                    self._adjust(change)
            self.topic_version = current_version
            self.id = f'{self.id}_adjust'

        def _adjust(self, change: StringChangeTypes.InsertChange | StringChangeTypes.DeleteChange):
            # we use a simple behavior on cursor movement:
            # only insert/delete before (exclusive) the cursor will affect the cursor position
            # this is also used by google docs and hackmd
            if isinstance(change, StringChangeTypes.InsertChange):
                ins_pos = change.position
                if ins_pos < self.position:
                    self.position += len(change.insertion)
            else:
                if change.position < self.position:
                    if change.position + len(change.deletion) <= self.position:
                        self.position -= min(len(change.deletion), self.position - change.position)
                    else:
                        self.position = change.position
                        self.insertion = ''

        def apply(self, old_value):
            try:
                return insert(old_value, self.position, self.insertion)
            except ValueError as e:
                raise InvalidChangeError(self, e.args[0]) from e

        def serialize(self) ->dict[str,Any]:
            return {"topic_name": self.topic_name, "topic_type": "string", "type": "insert", "topic_version": self.topic_version, "position": self.position, "insertion": self.insertion, "id": self.id}

        def inverse(self) -> Change:
            # TODO: here use the knowledge that a topic use a change's id to versioning
            # it's a duplication of knowledge
            return StringChangeTypes.DeleteChange(self.topic_name, self.id, self.position, self.insertion, self.topic_version)

        def __eq__(self, other):
            if not isinstance(other, StringChangeTypes.InsertChange):
                return False
            return self.topic_name == other.topic_name and \
                self.position == other.position and \
                self.insertion == other.insertion and \
                self.id == other.id

    class DeleteChange(Change):
        def __init__(self, topic_name: str, topic_version: str, position: int, deletion: str, id: Optional[str]=None):
            super().__init__(topic_name, id)
            self.position = position
            self.deletion = deletion
            self.topic_version = topic_version

        def sync_topic_version(self, current_version: str, topic: StringTopic):
            if self.topic_version == current_version:
                return

            try:
                changes = topic.changes_from(self.topic_version)
            except:
                raise InvalidChangeError(self, f"Invalid base topic version: {self.topic_version}")

            for change in changes:
                if isinstance(change, StringChangeTypes.SetChange):
                    # view it as delete all and insert all,
                    # the cursor should be at the beginning and no deletion will happen
                    self.position = 0
                    self.deletion = ''
                else:
                    self._adjust(change)
            self.topic_version = current_version
            self.id = f'{self.id}_adjust'


        def _adjust(self, change: StringChangeTypes.InsertChange | StringChangeTypes.DeleteChange):
            if isinstance(change, StringChangeTypes.DeleteChange):
                self.position, self.deletion = adjust_delete(
                    applied_start=change.position, applied_delete=change.deletion,
                    current_start=self.position, current_delete=self.deletion
                )
            elif isinstance(change, StringChangeTypes.InsertChange):
                if change.position <= self.position:
                    self.position += len(change.insertion)
                elif change.position < self.position + len(self.deletion):
                    self.deletion = extend_delete(self.deletion, at_pos=change.position - self.position, string=change.insertion)


        def apply(self, old_value):
            try:
                return delete(old_value, self.position, self.deletion)
            except ValueError as e:
                raise InvalidChangeError(self, e.args[0]) from e

        def serialize(self) ->dict[str,Any]:
            return {"topic_name": self.topic_name, "topic_type": "string", "topic_version": self.topic_version, "type": "delete", "position": self.position, "deletion": self.deletion, "id": self.id}

        def inverse(self) -> Change:
            # TODO: here use the knowledge that a topic use a change's id to versioning
            # it's a duplication of knowledge
            return StringChangeTypes.InsertChange(self.topic_name, self.id, self.position, self.deletion, self.topic_version)

        def __eq__(self, other):
            if not isinstance(other, StringChangeTypes.DeleteChange):
                return False
            return self.topic_name == other.topic_name and \
                self.position == other.position and \
                self.deletion == other.deletion and \
                self.id == other.id

    types = {'set':SetChange, 'insert': InsertChange, 'delete': DeleteChange}


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
        def __eq__(self, other):
            if not isinstance(other, IntChangeTypes.AddChange):
                return False
            return self.topic_name == other.topic_name and \
                self.value == other.value and \
                self.id == other.id

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
        def __eq__(self, other):
            if not isinstance(other, FloatChangeTypes.AddChange):
                return False
            return self.topic_name == other.topic_name and \
                self.value == other.value and \
                self.id == other.id

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
        def __eq__(self, other):
            if not isinstance(other, SetChangeTypes.AppendChange):
                return False
            return self.topic_name == other.topic_name and \
                self.item == other.item and \
                self.id == other.id

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
        def __eq__(self, other):
            if not isinstance(other, SetChangeTypes.RemoveChange):
                return False
            return self.topic_name == other.topic_name and \
                self.item == other.item and \
                self.id == other.id

    types = {'set':SetChange,'append':AppendChange,'remove':RemoveChange}

class ListChangeTypes:
    class SetChange(SetChange):
        def serialize(self):
            return {"topic_name":self.topic_name,"topic_type":"list","type":"set","value":self.value,"old_value":self.old_value,"id":self.id}

    class InsertChange(Change):
        def __init__(self,topic_name, item,position:int,id=None):
            super().__init__(topic_name,id)
            self.item = item
            self.position = position
        def apply(self, old_value:list):
            if self.position < 0:
                t=self.position
                self.position = len(old_value) + self.position + 1 # +1 because insert inserts before the position
            old_value.insert(self.position,self.item)
            return old_value
        def serialize(self):
            return {"topic_name":self.topic_name,"topic_type":"list","type":"insert","item":self.item,"position":self.position,"id":self.id}
        def inverse(self)->Change:
            return ListChangeTypes.PopChange(self.topic_name,self.position)
        def __eq__(self, other):
            if not isinstance(other, ListChangeTypes.InsertChange):
                return False
            return self.topic_name == other.topic_name and \
                self.item == other.item and \
                self.position == other.position and \
                self.id == other.id
    class PopChange(Change):
        def __init__(self,topic_name, position:int,id=None):
            super().__init__(topic_name,id)
            self.position = position
        def apply(self, old_value:list):
            if self.position < 0:
                self.position = len(old_value) + self.position
            self.item = old_value.pop(self.position)
            return old_value
        def serialize(self):
            return {"topic_name":self.topic_name,"topic_type":"list","type":"pop","position":self.position,"id":self.id}
        def inverse(self)->Change:
            return ListChangeTypes.InsertChange(self.topic_name,self.item,self.position)
        def __eq__(self, other):
            if not isinstance(other, ListChangeTypes.PopChange):
                return False
            return self.topic_name == other.topic_name and \
                self.position == other.position and \
                self.id == other.id

    types = {'set': SetChange, 'insert': InsertChange, 'pop': PopChange}

class DictChangeTypes:
    class SetChange(SetChange):
        def serialize(self):
            return {"topic_name":self.topic_name,"topic_type":"dict","type":"set","value":self.value,"old_value":self.old_value,"id":self.id}
    class AddChange(Change):
        def __init__(self,topic_name, key,value,id=None):
            super().__init__(topic_name,id)
            self.key = key
            self.value = value
        def apply(self, old_dict):
            if self.key in old_dict:
                raise InvalidChangeError(self,f'Adding {self.key} to {old_dict} would create a duplicate.')
            old_dict[self.key] = self.value
            return old_dict
        def serialize(self):
            return {"topic_name":self.topic_name,"topic_type":"dict","type":"add","key":self.key,"value":self.value,"id":self.id}
        def inverse(self)->Change:
            return DictChangeTypes.PopChange(self.topic_name,self.key)
        def __eq__(self, other):
            if not isinstance(other, DictChangeTypes.AddChange):
                return False
            return self.topic_name == other.topic_name and \
                self.key == other.key and \
                self.value == other.value and \
                self.id == other.id
    class PopChange(Change):
        def __init__(self,topic_name, key,id=None):
            super().__init__(topic_name,id)
            self.key = key
            self.value = None
        def apply(self, old_dict):
            if self.key not in old_dict:
                raise InvalidChangeError(self,f'{self.key} is not in {old_dict}')
            self.value = old_dict.pop(self.key)
            return old_dict
        def serialize(self):
            return {"topic_name":self.topic_name,"topic_type":"dict","type":"pop","key":self.key,"id":self.id}
        def inverse(self)->Change:
            return DictChangeTypes.AddChange(self.topic_name,self.key,self.value)
        def __eq__(self, other):
            if not isinstance(other, DictChangeTypes.PopChange):
                return False
            return self.topic_name == other.topic_name and \
                self.key == other.key and \
                self.id == other.id
    class ChangeValueChange(Change):
        def __init__(self,topic_name, key,value,old_value=None,id=None):
            super().__init__(topic_name,id)
            self.key = key
            self.value = value
            self.old_value = old_value
        def apply(self, old_dict):
            if self.key not in old_dict:
                raise InvalidChangeError(self,f'{self.key} is not in {old_dict}')
            if self.old_value != old_dict[self.key]:
                # regenerate id
                self.id = IdGenerator.generate_id()
            self.old_value = old_dict[self.key]
            old_dict[self.key] = self.value
            return old_dict
        def serialize(self):
            return {"topic_name":self.topic_name,"topic_type":"dict","type":"change_value","key":self.key,"value":self.value,"old_value":self.old_value,"id":self.id}
        def inverse(self)->Change:
            return DictChangeTypes.ChangeValueChange(self.topic_name,self.key,self.old_value,self.value)
        def __eq__(self, other):
            if not isinstance(other, DictChangeTypes.ChangeValueChange):
                return False
            return self.topic_name == other.topic_name and \
                self.key == other.key and \
                self.value == other.value and \
                self.old_value == other.old_value and \
                self.id == other.id
    types = {'set':SetChange,'add':AddChange,'pop':PopChange,'change_value':ChangeValueChange}

class EventChangeTypes:
    class EmitChange(Change):
        def __init__(self,topic_name,args={},forward_info={},id=None):
            super().__init__(topic_name,id)
            self.args = args
            self.forward_info = forward_info
        def apply(self,old_value:None):
            return None
        def serialize(self):
            return {"topic_name":self.topic_name,"topic_type":"event","type":"emit","args":self.args,"forward_info":self.forward_info,"id":self.id}
        def inverse(self)->Change:
            return EventChangeTypes.ReversedEmitChange(self.topic_name,self.args,self.forward_info)
        def __eq__(self, other):
            if not isinstance(other, EventChangeTypes.EmitChange):
                return False
            return self.topic_name == other.topic_name and \
                self.args == other.args and \
                self.forward_info == other.forward_info and \
                self.id == other.id
    class ReversedEmitChange(Change):
            def __init__(self,topic_name,args={},forward_info={},id=None):
                super().__init__(topic_name,id)
                self.args = args
                self.forward_info = forward_info
            def apply(self,old_value:None):
                return None
            def serialize(self):
                return {"topic_name":self.topic_name,"topic_type":"event","type":"reversed_emit","args":self.args,"forward_info":self.forward_info,"id":self.id}
            def inverse(self)->Change:
                return EventChangeTypes.EmitChange(self.topic_name,self.args)
            def __eq__(self, other):
                if not isinstance(other, EventChangeTypes.ReversedEmitChange):
                    return False
                return self.topic_name == other.topic_name and \
                    self.args == other.args and \
                    self.forward_info == other.forward_info and \
                    self.id == other.id
    types = {'emit':EmitChange,'reversed_emit':ReversedEmitChange}

type_name_to_change_types = {
                                'generic':GenericChangeTypes,
                                'string':StringChangeTypes,
                                'int':IntChangeTypes,
                                'float':FloatChangeTypes,
                                'set':SetChangeTypes,
                                'dict':DictChangeTypes,
                                'list':ListChangeTypes,
                                'event':EventChangeTypes
                            }
