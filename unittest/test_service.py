import unittest
from chatroom import ChatroomRouter, ChatroomClient
import time

class TestService(unittest.TestCase):
    def test_service(self):
        server = ChatroomRouter(start_thread=True)
        client1 = ChatroomClient(start=True,log_prefix="client1")
        client2 = ChatroomClient(start=True,log_prefix="client2")

        for i in range(10):
            def add_i(x,i=i):
                return x + i
            client1.RegisterService(f'add_{i}', add_i)
        time.sleep(0.3)
        
        self.result = [None]*10
        for i in range(10):
            def on_response(x,i=i):
                print("Got response", x)
                self.result[i] = x
            client2.MakeRequest(f"add_{i}", {"x": 1}, on_response)
        while None in self.result:
            time.sleep(0.1)
        for i in range(10):
            self.assertEqual(self.result[i], i+1)

        client2.RegisterService("hello", lambda x: f"Hello {x}")
        time.sleep(0.3)
        self.result = None
        def on_response(x):
            print("Got response", x)
            self.result = x
        client1.MakeRequest("hello", {"x": "eric"}, on_response)
        while self.result is None:
            time.sleep(0.1)
        self.assertEqual(self.result, "Hello eric")

    

