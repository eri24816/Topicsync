

import time

import threading
#server = ChatroomServer(start_thread=True)
client1 = ChatroomClient(start=True,log_prefix="client1")

client2 = ChatroomClient(start=True,log_prefix="client2")

client1.RegisterService("add_one", lambda x: x + 2)
# print(client1._sending_queue.qsize())
# time.sleep(0.3)
# client2.MakeRequest("add_one", {"x": 1}, lambda x: print("Got response", x))
# time.sleep(5)
# print(client1._sending_queue.qsize())

#client = ChatroomClient(start=True,log_prefix="client1")

#client1.RegisterService("add_one", lambda x: x + 2)
time.sleep(120000)