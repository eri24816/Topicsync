from chatroom.utils import EventWithData
from typing import Dict
class EventManager:
    def __init__(self) -> None:
        self._event_pool:Dict[str,EventWithData] = {}
    def Wait(self,name):
        event = self._event_pool[name] = EventWithData()
        return event.wait()
    def Resume(self,name,data=None):
        return self._event_pool.pop(name).set(data)