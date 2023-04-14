from chatroom import ChatroomServer

import asyncio

from chatroom.topic import StringTopic

server = ChatroomServer(8765,lambda x:None)
server.AddTopic("a",StringTopic)
asyncio.run(server.Serve())
