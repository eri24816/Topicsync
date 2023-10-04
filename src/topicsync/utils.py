import asyncio
import json
from typing import Any, Callable, Dict, List, Optional, Tuple
import typing

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

def make_message(message_type,**kwargs)->str:
    return json.dumps({"type":message_type,"args":kwargs})

def parse_message(message_json)->Tuple[str,dict]:
    message = json.loads(message_json)
    return message["type"],message["args"]

class Action:
    '''
    A hub for callbacks
    '''
    def __init__(self):
        self._auto_callbacks:List[Callable] = []
        self._manual_callbacks:List[Callable] = []
        self._raw_callbacks:List[Callable] = []
        self.num_callbacks = 0

    def __add__(self,callback:Callable):
        '''
        Temporary backward compatibility. To be removed.
        '''
        self.add(callback) 
        return self
    
    def __sub__(self,callback:Callable):
        '''
        Temporary backward compatibility. To be removed.
        '''
        self.remove(callback)
        return self
    
    def add(self,callback:Callable,auto=False):
        if auto:
            self._auto_callbacks.append(callback)
        else:
            self._manual_callbacks.append(callback)
        self.num_callbacks += 1

    def add_manual(self,callback:Callable):
        self._manual_callbacks.append(callback)
        self.num_callbacks += 1

    def add_auto(self,callback:Callable):
        self._auto_callbacks.append(callback)
        self.num_callbacks += 1

    def add_raw(self,callback:Callable):
        self._raw_callbacks.append(callback)
        self.num_callbacks += 1

    def remove(self,callback:Callable):
        if callback in self._manual_callbacks:
            self._manual_callbacks.remove(callback)
        elif callback in self._auto_callbacks:
            self._auto_callbacks.remove(callback)
        elif callback in self._raw_callbacks:
            self._raw_callbacks.remove(callback)
        else:
            raise ValueError("Callback not found")
        self.num_callbacks -= 1
    
    def invoke(self, auto, *args: Any, **kwargs: Any) -> Any:
        '''Call each callback in the action with the given arguments.'''
        returns = []
        callback_list = self._auto_callbacks if auto else self._manual_callbacks
        for callback in callback_list:
            returns.append(callback(*args,**kwargs))
        for callback in self._raw_callbacks:
            returns.append(callback(auto,*args,**kwargs))
        return returns

import weakref
_KT = typing.TypeVar("_KT") #  key type
_VT = typing.TypeVar("_VT") #  value type
class WeakKeyDict(weakref.WeakValueDictionary[_KT, _VT]):
    '''
    It is weakref.WeakValueDictionary but calls a callback when an item is removed. The callback is called with the key of the removed item.
    '''
    def __init__(self, on_removed:Optional[Callable[[str],None]]=None):
        super().__init__()
        self.cb = on_removed

        def new_remove(el:weakref.KeyedRef, selfref=weakref.ref(self)):
            self = selfref()
            if self is not None:
                if self.cb is not None:
                    self.cb(el.key)
                self._old_remove(el)

        self._old_remove = self._remove
        self._remove = new_remove

    
def camel_to_snake(name):
    return ''.join(['_'+c.lower() if c.isupper() else c for c in name]).lstrip('_')

T = typing.TypeVar('T')
def astype(value:Any,type_:type[T])->T:
    if isinstance(value,type_):
        return value
    else:
        raise TypeError(f"{type(value)} is not subtype of {type_}")

class IdGenerator:
    instance = None
    @staticmethod
    def generate_id():
        if IdGenerator.instance is None:
            IdGenerator.instance = IdGenerator()
        return IdGenerator.instance()
    def __init__(self):
        self._id = 0
    def __call__(self):
        self._id += 1
        return '0_'+str(self._id) # 0 means server

class SimpleAction:
    '''
    A hub for callbacks.
    Difference from `Action` class: no auto/manual distinction.
    '''
    def __init__(self):
        self.callbacks:List[Callable] = []

    def __add__(self,callback:Callable):
        '''
        Temporary backward compatibility. To be removed.
        '''
        self.callbacks.append(callback)
        return self
    
    def __sub__(self,callback:Callable):
        '''
        Temporary backward compatibility. To be removed.
        '''
        self.callbacks.remove(callback)
        return self
    
    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        '''Call each callback in the action with the given arguments.'''
        returns = []
        for callback in self.callbacks:
            returns.append(callback(*args,**kwargs))
        return returns

class Clock:
    def __init__(self, interval: float):
        '''
        Interval is in seconds.
        '''
        self.interval = interval
        self.on_tick = SimpleAction()

    async def run(self):
        while True:
            await asyncio.sleep(self.interval)
            self.on_tick.invoke()