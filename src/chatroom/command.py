from __future__ import annotations
import contextlib
import json
from typing import Any, Callable, TYPE_CHECKING
from chatroom.topic_change import Change
if TYPE_CHECKING:
    from chatroom.topic import Topic


class Command:
    def __init__(self) -> None:
        pass
    def Execute(self):
        raise NotImplementedError
    def Undo(self):
        raise NotImplementedError
    def Redo(self):
        raise NotImplementedError

class ChangeCommand(Command):
    @staticmethod
    def Deserialize(data:dict[str,Any],get_topic_by_name:Callable[[str],Topic])->ChangeCommand:
        return ChangeCommand(data['topic_name'],Change.Deserialize(data['change']),get_topic_by_name)
    
    def __init__(self,topic_name:str,change:Change,get_topic_by_name:Callable[[str],Topic]) -> None:
        super().__init__()
        self.get_topic_by_name = get_topic_by_name
        self.topic_name = topic_name # Note the topic name is stored to avoid reference to a topic object to be deleted. #TODO: test this
        self.change = change
    def Execute(self):
        self.get_topic_by_name(self.topic_name).ApplyChange(self.change)
    def Undo(self):
        self.get_topic_by_name(self.topic_name).ApplyChange(self.change.Inverse())
    def Redo(self):
        self.get_topic_by_name(self.topic_name).ApplyChange(self.change)
    def Serialize(self):
        return {
            'topic_name':self.topic_name,
            'change':self.change.Serialize()
        }
