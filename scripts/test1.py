
from topicsync import TopicsyncServer, HistoryManager

import asyncio

from topicsync.topic import FloatTopic, IntTopic, StringTopic, SetTopic, GenericTopic

server = TopicsyncServer(8765)

a=server.add_topic('a',FloatTopic)
b=server.add_topic('b',FloatTopic)

a.on_set += lambda x: b.set(x*2)

asyncio.run(server.serve())
