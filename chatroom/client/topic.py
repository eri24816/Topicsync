from __future__ import annotations
from collections import deque
from typing import Deque, Dict
from typing import Callable, List, TYPE_CHECKING
from itertools import count
if TYPE_CHECKING:
    from .client import ChatroomClient
from chatroom.topic_change import Change, ChangeSet
import abc

def camel_to_snake(name):
    return ''.join(['_'+c.lower() if c.isupper() else c for c in name]).lstrip('_')

class Topic(metaclass = abc.ABCMeta):

    def __init__(self,name,client:ChatroomClient):
        self.client = client
        self._name = name
        self._value = None
        self._preview_changes : Dict[int,Change] = {}
        self._preview_path : Deque[Change] = deque()
        
        self._set_listeners : List[Callable] = []

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
        return self._value
    
    def AddSetListener(self, listener):
        self._set_listeners.append(listener)

    def RemoveSetListener(self, listener):
        self._set_listeners.remove(listener)
    # child classes (other types of topics) will allow more change types thus more Add/Remove methods
    
    def Set(self, value):
        '''
        This is a basic topic-changing method that all topic types support. For different types of topics, there can be more topic-changing method.
        All topic-changing methods should summon a Change and call _UpdateByUser to send the change to server and setup the preview.
        '''
        change = ChangeSet(value)
        self._UpdateByUser(change)
        
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
        self._preview_path.append(change)
        self._ChangeDisplayValue(change)

        # send the change to server
        self.client.Update(self.GetName(), change.Serialize())
    
    def _ChangeDisplayValue(self, change:Change):
        '''
        Set the display value and notify listeners
        '''
        self._value = change.Apply(self._value)
        self._NotifyListeners(change)

    '''
    Abstract/virtual methods
    '''

    @abc.abstractmethod
    def _NotifyListeners(self,change:Change):
        # notify user-side listeners for a topic change. Every listener type work differently. Override this method in child classes to notify listeners of different types.
        pass

    '''
    ws inbound interface
    '''
    def Update(self, change_dict):

        change = Change.Deserialize(change_dict) # first obtain the change object

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
        if self._preview_path[0].id == change_dict['id']:
            while len(self._preview_path)>0:
                self._ChangeDisplayValue(self._preview_path.pop().Inverse())
        
class StringTopic(Topic):
    '''
    StringTopic is a topic that has a string value.
    '''
    def __init__(self,name,client:ChatroomClient):
        super().__init__(name,client)
        if self._value is None:
            self._value = ''
        self._set_listeners : List[Callable[[str],None]] = []

    def _NotifyListeners(self,change:ChangeSet):
        for listener in self._set_listeners:
            listener(change.value)