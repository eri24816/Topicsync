import unittest
from chatroom import ChatroomServer, ChatroomClient
import time

from chatroom.client.topic import StringTopic
from utils import get_free_port

class TestTopic(unittest.TestCase):
    def test_subscribe(self):
        port = get_free_port()
        server = ChatroomServer(start_thread=True,port = port)
        client1 = ChatroomClient(start=True,log_prefix="client1",port = port)
        client2 = ChatroomClient(start=True,log_prefix="client2",port = port)

        a1 = client1.RegisterTopic(StringTopic, "a")
        time.sleep(0.1)
        a2 = client2.RegisterTopic(StringTopic, "a")
        a1.Set("hello")
        time.sleep(0.1)
        self.assertEqual(a2.GetValue(), "hello")

    def test_post_subscribe(self):
        port = get_free_port()
        server = ChatroomServer(start_thread=True,port = port)
        client1 = ChatroomClient(start=True,log_prefix="client1",port = port)
        client2 = ChatroomClient(start=True,log_prefix="client2",port = port)

        a1 = client1.RegisterTopic(StringTopic, "a")
        a1.Set("hello")
        time.sleep(0.1)
        a2 = client2.RegisterTopic(StringTopic, "a")
        time.sleep(0.1)
        self.assertEqual(a2.GetValue(), "hello")

    def test_react(self):
        port = get_free_port()
        server = ChatroomServer(start_thread=True,port = port)
        client1 = ChatroomClient(start=True,log_prefix="client1",port = port)
        client2 = ChatroomClient(start=True,log_prefix="client2",port = port)

        a1 = client1.RegisterTopic(StringTopic, "a")
        a2 = client2.RegisterTopic(StringTopic, "a")
        b1 = client1.RegisterTopic(StringTopic, "b")
        b2 = client2.RegisterTopic(StringTopic, "b")

        a2.on_set += lambda x: b2.Set(x + " world")
        a1.Set("hello")
        time.sleep(0.1)
        self.assertEqual(b1.GetValue(), "hello world")

    def test_broadcast(self):
        port = get_free_port()
        server = ChatroomServer(start_thread=True,port = port)
        sender = ChatroomClient(start=True,log_prefix="client1",port = port)
        recievers = [ChatroomClient(start=True,log_prefix=f"client{i}",port = port) for i in range(10)]

        a1 = sender.RegisterTopic(StringTopic, "a")
        a = [r.RegisterTopic(StringTopic, "a") for r in recievers]
        a1.Set("hello")
        time.sleep(0.1)
        for i in range(10):
            self.assertEqual(a[i].GetValue(), "hello")

    def test_reject(self):
        port = get_free_port()
        server = ChatroomServer(start_thread=True,port = port)
        sender = ChatroomClient(start=True,log_prefix="sender",port = port)
        autority = ChatroomClient(start=True,log_prefix="autority",port = port)
        reciever = ChatroomClient(start=True,log_prefix="reciever",port = port)

        sender_topic = sender.RegisterTopic(StringTopic, "a")
        reciever_topic = reciever.RegisterTopic(StringTopic, "a")

        autority.RegisterService('_chatroom/validate_change/a', lambda *args,**kwargs: {'valid': False,'reason': 'You is the because'})
        time.sleep(0.1)
        sender_topic.Set("hello")
        time.sleep(0.1)
        self.assertEqual(reciever_topic.GetValue(), '')
        self.assertEqual(sender_topic.GetValue(), '')

    def test_conditonal_reject(self):
        port = get_free_port()
        server = ChatroomServer(start_thread=True,port = port)
        sender = ChatroomClient(start=True,log_prefix="sender",port = port)
        autority = ChatroomClient(start=True,log_prefix="autority",port = port)
        reciever = ChatroomClient(start=True,log_prefix="reciever",port = port)

        sender_topic = sender.RegisterTopic(StringTopic, "guess_a_number")
        reciever_topic = reciever.RegisterTopic(StringTopic, "guess_a_number")

        def validate_change(change):
            # only accept numbers between 0 and 100
            if int(change['value']) > 100:
                return {'valid': False,'reason': 'Too big'}
            elif int(change['value']) < 0:
                return {'valid': False,'reason': 'Too small'}
            else:
                return {'valid': True}
            
        autority.RegisterService('_chatroom/validate_change/guess_a_number', validate_change)
        time.sleep(0.1)

        sender_topic.Set("87")
        time.sleep(0.1)
        self.assertEqual(reciever_topic.GetValue(), '87')
        self.assertEqual(sender_topic.GetValue(), '87')
        
        sender_topic.Set("101")
        time.sleep(0.1)
        self.assertEqual(reciever_topic.GetValue(), '87')
        self.assertEqual(sender_topic.GetValue(), '87')

        sender_topic.Set("-1")
        time.sleep(0.1)
        self.assertEqual(reciever_topic.GetValue(), '87')
        self.assertEqual(sender_topic.GetValue(), '87')

        sender_topic.Set("5")
        time.sleep(0.1)
        self.assertEqual(reciever_topic.GetValue(), '5')
        self.assertEqual(sender_topic.GetValue(), '5')



        
    

