import asyncio
import json
from typing import Tuple

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
    
def MakeMessage(message_type,**kwargs)->str:
    return json.dumps({"type":message_type,"args":kwargs})

def ParseMessage(message_json)->Tuple[str,dict]:
    message = json.loads(message_json)
    return message["type"],message["args"]