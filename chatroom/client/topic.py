from typing import Callable, List, TYPE_CHECKING
from itertools import count
if TYPE_CHECKING:
    from .client import ChatroomClient

class Topic:
    def __init__(self,name,client:ChatroomClient):
        self.client = client
        self._name = name
        self._value = None
        self._listeners : List[Callable] = []
        self._preview_pool : List[TopicChange] = []
        self._display_value = None
        self.client.Subscribe(self._name)

    '''
    Public methods
    '''
    def GetName(self):
        return self._name

    def AddListener(self, listener):
        if len(self._listeners) == 0:
            self.client.Subscribe(self._name)
        self._listeners.append(listener)

    def RemoveListener(self, listener):
        self._listeners.remove(listener)
        if len(self._listeners) == 0:
            self.client.Unsubscribe(self._name)

    def SetValue(self, value):
        change = TopicChangeRaw(self, value)
        self._preview_pool.append(change)
        self._display_value = change.Apply(self._display_value)
        self.client.TryPublish(self, change)

    '''
    ws interfaces
    '''
    # inbound
    def Update(self, change, source):
        self._value = change.Apply(self._value)
        
        if source == self.client.GetID(): # self's change has been accepted. Remove the preview from preview pool
            for preview in self._preview_pool:
                if preview.id == change.id:
                    self._preview_pool.remove(preview)
                    break

        if len(self._preview_pool) == 0: # no preview left, display the actual value
            self._display_value = self._value
        
class TopicChange:
    id_generator = count()
    @staticmethod
    def Deserialize(data):
        if data["type"] == "raw":
            return TopicChangeRaw(data["topic"], data["value"])

    def __init__(self, topic:Topic):
        self._topic = topic
        self.id = next(TopicChange.id_generator)

    def Serialize(self) -> dict:
        return {}

    def Apply(self, old_value):
        pass

class TopicChangeRaw(TopicChange):
    def __init__(self, topic:Topic, value):
        super().__init__(topic)
        self._value = value

    def Serialize(self):
        return {"type": "raw", "topic": self._topic.GetName() , "value": self._value}

    def Apply(self, old_value):
        return self._value