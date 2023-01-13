import chatroom
import time
client = chatroom.ChatroomClient("ws://localhost:8765")
client.Start()


client.MakeRequest("echo",{'name':"eric"},lambda response: print('Got response',response))

time.sleep(120000)