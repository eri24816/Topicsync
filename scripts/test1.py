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

server.RegisterService('add',lambda a,b: a+b)
server.RegisterService('greet',lambda name: 'Hello '+name)

server.AddTopic("a",StringTopic)
s=server.AddTopic("s",SetTopic)
t=server.AddTopic("t",SetTopic)
t.on_append += lambda value: s.Append(value+'!')
t.on_remove += lambda value: s.Remove(value+'!')
s.on_append += lambda value: t.Append(value[:-1])
s.on_remove += lambda value: t.Remove(value[:-1])
t.Append("hello")
asyncio.run(server.Serve())
