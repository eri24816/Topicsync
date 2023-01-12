import chatroom
import time
client = chatroom.ChatroomClient("ws://localhost:8765")
client.Run()

client.RegisterService("echo",lambda name: f"Hello {name}")

time.sleep(120000)