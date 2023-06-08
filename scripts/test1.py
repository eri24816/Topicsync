import logging
logger = logging.getLogger(__name__)
from chatroom import ChatroomServer, HistoryManager

import asyncio

from chatroom.topic import FloatTopic, IntTopic, StringTopic, SetTopic, GenericTopic

# client.makeRequest('add', {a:1,b:2}, (response: any) => {
#     print('1+2=',response);
# });
# client.makeRequest('greet', {name:'Eric'}, (response: any) => {
#     print(response);
# });
logging.basicConfig(level=logging.INFO)
history = HistoryManager()
server = ChatroomServer(8765,on_transition_done = history.add_transition)
history.set_server(server)

server.register_service('undo',history.undo)
server.register_service('redo',history.redo)


server.register_service('add',lambda a,b: a+b)
server.register_service('greet',lambda name: 'Hello '+name)


server.add_topic("a",StringTopic)
s=server.add_topic("s",SetTopic)
t=server.add_topic("t",SetTopic)
t.on_append += lambda value: s.append(value+'!')
t.on_remove += lambda value: s.remove(value+'!')
s.on_append += lambda value: t.append(value[:-1])
s.on_remove += lambda value: t.remove(value[:-1])
t.append("hello")

i = server.add_topic("i",IntTopic)
f = server.add_topic("f",FloatTopic)

g1 = server.add_topic("g1",GenericTopic[float])
g2 = server.add_topic("g2",GenericTopic[dict[str,list]],init_value={'a':[1,2,3]})
g1.set(1.0)


asyncio.run(server.serve())
