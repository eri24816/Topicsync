import asyncio
import json
from typing import Any, Callable, Dict, List, Tuple, Union

class EventWithData(asyncio.Event):
    def __init__(self):
        super().__init__()
        self.data = None

    def set(self, data):
        self.data = data
        super().set()

    def clear(self):
        self.data = None
        super().clear()

    async def wait(self):
        await super().wait()
        return self.data

class EventManager:
    def __init__(self) -> None:
        self._event_pool:Dict[str,EventWithData] = {}
    def Wait(self,name):
        event = self._event_pool[name] = EventWithData()
        return event.wait()
    def Resume(self,name,data=None):
        return self._event_pool.pop(name).set(data)

def MakeMessage(message_type,**kwargs)->str:
    return json.dumps({"type":message_type,"args":kwargs})

def ParseMessage(message_json)->Tuple[str,dict]:
    message = json.loads(message_json)
    return message["type"],message["args"]

class Action:
    '''
    A hub for callbacks
    '''
    def __init__(self):
        self._callbacks:List[Callable] = []

    def __add__(self,callback:Callable):
        self._callbacks.append(callback)
        return self
    
    def __sub__(self,callback:Callable):
        self._callbacks.remove(callback)
        return self
    
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        '''Call each callback in the action with the given arguments.'''
        for callback in self._callbacks:
            callback(*args,**kwargs)

class ActionGroup:
    '''
    A group of specific number of actions. When using _add_ or _sub_, you need to pass in a list of callbacks for each action.
    '''
    def __init__(self,n:int):
        self._actions:List[Action] = [Action() for _ in range(n)]
    
    def __getitem__(self,index):
        return self._actions[index]
    
    def __len__(self):
        return len(self._actions)
    
    def __add__(self,callbacks:List[Callable]):
        for action,callback in zip(self._actions,callbacks):
            action += callback
        return self
    
    def __sub__(self,callbacks:List[Callable]):
        for action,callback in zip(self._actions,callbacks):
            action -= callback
        return self

    
def camel_to_snake(name):
    return ''.join(['_'+c.lower() if c.isupper() else c for c in name]).lstrip('_')