from __future__ import annotations
from collections import deque
import copy
from typing import Deque, Dict, Tuple
from typing import Callable, List, TYPE_CHECKING
from itertools import count
if TYPE_CHECKING:
    from .client import ChatroomClient
from chatroom.topic_change import Change, StringChangeTypes, UListChangeTypes, default_topic_value
from chatroom.utils import Action, camel_to_snake
import abc

class Topic(metaclass = abc.ABCMeta):

    def __init__(self,name,client:ChatroomClient):
        self.client = client
        self._name = name
        self._value = default_topic_value[self.GetTypeName()]
        self._preview_changes : Dict[int,Change] = {}
        self._preview_path : Deque[Change] = deque()

    def __del__(self):
        self.client.Unsubscribe(self._name)
        
    '''
    User-side methods
    '''

    def GetName(self):
        return self._name
    
    def GetTypeName(self):
        return camel_to_snake(self.__class__.__name__.replace('Topic',''))
    
    def GetValue(self):
        return copy.deepcopy(self._value)
        
    '''
    Private methods
    '''

    def _UpdateByUser(self, change:Change):
        '''
        Call this when the user want to change the value of the topic.
        This method will send the change to server and wait for the server to approve it.
        Before the server approves it, the change will be previewed. The preview history is stored in _preview_path.
        After the server approves the change, the change will be popped (identified by the id).
        If the server rejects the change, all the changes in the preview history will be reversed and cleared.
        '''
        if not self._ChangeDisplayValue(change):
            return
        
        self._preview_path.append(change)
        # send the change to server
        self.client.Update(self.GetName(), change.Serialize())
    
    def _ChangeDisplayValue(self, change:Change):
        '''
        Set the display value and notify listeners. Return False if the change is invalid.
        '''
        old_value = self._value
        try:
            self._value = change.Apply(self._value)
        except Exception as e:
            print('invalid change',e)
            return False
        self._NotifyListeners(change,old_value=old_value,new_value=self._value)
        return True

    '''
    Abstract/virtual methods
    '''

    @abc.abstractmethod
    def _NotifyListeners(self,change:Change, old_value, new_value):
        # notify user-side listeners for a topic change. Every listener type work differently. Override this method in child classes to notify listeners of different types.
        pass

    '''
    ws inbound interface
    '''
    def Update(self, change_dict):

        change = Change.Deserialize(self.GetTypeName(),change_dict) # first obtain the change object

        if len(self._preview_path)>0 and change.id == self._preview_path[0].id: 
            # if the oldest previewing change is approved by server
            # pop the change from preview history
            self._preview_path.popleft() 
            return # the result of the change is already displayed. Keep the preview. No need to do anything else.
        else: 
            # if the change is not the oldest entry in the preview history, it's a new change from another client. 
            # All preview changes should be reversed before applying the incoming change.
            while len(self._preview_path)>0:
                self._ChangeDisplayValue(self._preview_path.pop().Inverse())
            self._ChangeDisplayValue(change) # apply the new change
            return
        
    def UpdateRejected(self, change_dict):
        # if the change is rejected by server, the change and all preview changes after it should be reversed.
        if len(self._preview_path) > 0 and self._preview_path[0].id == change_dict['id']:
            while len(self._preview_path)>0:
                self._ChangeDisplayValue(self._preview_path.pop().Inverse())
        
class StringTopic(Topic):
    '''
    String topic
    '''
    def __init__(self,name,client:ChatroomClient):
        super().__init__(name,client)
        self.on_set = Action()
    
    def Set(self, value):
        change = StringChangeTypes.SetChange(value)
        self._UpdateByUser(change)

    def _NotifyListeners(self,change:Change, old_value, new_value):
        if isinstance(change,StringChangeTypes.SetChange):
            self.on_set(new_value)
        else:
            raise Exception(f'Unsupported change type {type(change)} for StringTopic')

class UListTopic(Topic):
    '''
    Unordered list topic
    '''
    def __init__(self,name,client:ChatroomClient):
        super().__init__(name,client)
        self.on_set = Action()
        self.on_append = Action()
        self.on_remove = Action()
    
    def Set(self, value):
        change = UListChangeTypes.SetChange(value)
        self._UpdateByUser(change)

    def Append(self, item):
        change = UListChangeTypes.AppendChange(item)
        self._UpdateByUser(change)

    def Remove(self, item):
        change = UListChangeTypes.RemoveChange(item)
        self._UpdateByUser(change)        

    def __getitem__(self, index):
        return copy.deepcopy(self._value[index])
    
    def __len__(self):
        return len(self._value)

    def _NotifyListeners(self,change:Change, old_value, new_value):
        if isinstance(change,UListChangeTypes.SetChange):
            self.on_set(new_value)
            for item in old_value:
                self.on_remove(item)
            for item in new_value:
                self.on_append(item)
        elif isinstance(change,UListChangeTypes.AppendChange):
            self.on_set(new_value)
            self.on_append(change.item)
        elif isinstance(change,UListChangeTypes.RemoveChange):
            self.on_set(new_value)
            self.on_remove(change.item)
        else:
            raise Exception(f'Unsupported change type {type(change)} for UListTopic')