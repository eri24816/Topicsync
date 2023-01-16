import unittest
from chatroom import ChatroomServer, ChatroomClient
import time

from chatroom.client.topic import StringTopic

class TestTopic(unittest.TestCase):
    def test_subscribe(self):
        server = ChatroomServer(start_thread=True)
        client1 = ChatroomClient(start=True,log_prefix="client1")
        client2 = ChatroomClient(start=True,log_prefix="client2")

        a1 = client1.RegisterTopic(StringTopic, "a")
        time.sleep(0.1)
        a2 = client2.RegisterTopic(StringTopic, "a")
        a1.Set("hello")
        time.sleep(0.1)
        self.assertEqual(a2.GetValue(), "hello")

    def test_post_subscribe(self):
        server = ChatroomServer(start_thread=True)
        client1 = ChatroomClient(start=True,log_prefix="client1")
        client2 = ChatroomClient(start=True,log_prefix="client2")

        a1 = client1.RegisterTopic(StringTopic, "a")
        a1.Set("hello")
        time.sleep(0.1)
        a2 = client2.RegisterTopic(StringTopic, "a")
        time.sleep(0.1)
        self.assertEqual(a2.GetValue(), "hello")

    def test_react(self):
        server = ChatroomServer(start_thread=True)
        client1 = ChatroomClient(start=True,log_prefix="client1")
        client2 = ChatroomClient(start=True,log_prefix="client2")

        a1 = client1.RegisterTopic(StringTopic, "a")
        a2 = client2.RegisterTopic(StringTopic, "a")
        b1 = client1.RegisterTopic(StringTopic, "b")
        b2 = client2.RegisterTopic(StringTopic, "b")

        a2.AddSetListener(lambda x: b2.Set(x + " world"))
        a1.Set("hello")
        time.sleep(0.1)
        self.assertEqual(b1.GetValue(), "hello world")

    def test_broadcast(self):
        server = ChatroomServer(start_thread=True)
        sender = ChatroomClient(start=True,log_prefix="client1")
        recievers = [ChatroomClient(start=True,log_prefix=f"client{i}") for i in range(10)]

        a1 = sender.RegisterTopic(StringTopic, "a")
        a = [r.RegisterTopic(StringTopic, "a") for r in recievers]
        a1.Set("hello")
        time.sleep(0.1)
        for i in range(10):
            self.assertEqual(a[i].GetValue(), "hello")
    

