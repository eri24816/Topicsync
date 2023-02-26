from chatroom import ChatroomServer
from chatroom import topic

server = ChatroomServer(8766)
server.RegisterService('add',lambda a,b: a+b)
server.RegisterService('greet',lambda name: f"Hello {name}")
a=server.RegisterTopic('a',topic.StringTopic)
a.AddValidator(lambda old,new,change: len(new) <= 3)

import time
time.sleep(120000)