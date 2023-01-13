import asyncio

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