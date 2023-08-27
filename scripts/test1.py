
from chatroom import ChatroomServer, HistoryManager

import asyncio

from chatroom.topic import FloatTopic, IntTopic, StringTopic, SetTopic, GenericTopic

server = ChatroomServer(8765)

a=server.add_topic('a',FloatTopic)
b=server.add_topic('b',FloatTopic)

a.on_set += lambda x: b.set(x*2)

asyncio.run(server.serve())
