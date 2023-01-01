import chatroom
import time
client = chatroom.ChatroomClient("ws://localhost:8765")
client.Run()

client.AddTopicHandler("test",lambda payload:print(f"Received {payload}"))

client.Publish("test","3")

client.Publish("test","4")

time.sleep(1200)