from chatroom import ChatroomServer

import asyncio

from chatroom.topic import StringTopic, SetTopic

# client.makeRequest('add', {a:1,b:2}, (response: any) => {
#     print('1+2=',response);
# });
# client.makeRequest('greet', {name:'Eric'}, (response: any) => {
#     print(response);
# });
server = ChatroomServer(8765,lambda x:None)

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
asyncio.run(server.serve())
