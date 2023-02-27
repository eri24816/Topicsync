import json
import unittest
from chatroom import ChatroomServer, ChatroomClient
import time

from chatroom.topic import StringTopic, SetTopic
from utils import get_free_port, Empty, random_combinations

class TestTopic(unittest.TestCase):
    def test_subscribe(self):
        port = get_free_port()
        server = ChatroomServer(port = port)
        client1 = ChatroomClient(start=True,log_prefix="client1",port = port)
        client2 = ChatroomClient(start=True,log_prefix="client2",port = port)
        server.RegisterTopic('a',StringTopic)
        a1 = client1.RegisterTopic('a',StringTopic)
        time.sleep(0.1)
        a2 = client2.RegisterTopic('a',StringTopic)
        a1.Set("hello")
        time.sleep(0.1)
        self.assertEqual(a1.GetValue(), "hello")
        self.assertEqual(a2.GetValue(), "hello")

    def test_post_subscribe(self):
        port = get_free_port()
        server = ChatroomServer(port = port)
        client1 = ChatroomClient(start=True,log_prefix="client1",port = port)
        client2 = ChatroomClient(start=True,log_prefix="client2",port = port)
        
        server.RegisterTopic('a',StringTopic)
        a1 = client1.RegisterTopic('a',StringTopic)
        a1.Set("hello")
        time.sleep(0.1)
        a2 = client2.RegisterTopic('a',StringTopic)
        time.sleep(0.1)
        self.assertEqual(a2.GetValue(), "hello")

    def test_react(self):
        port = get_free_port()
        server = ChatroomServer(port = port)
        client1 = ChatroomClient(start=True,log_prefix="client1",port = port)
        client2 = ChatroomClient(start=True,log_prefix="client2",port = port)
        
        server.RegisterTopic('a',StringTopic)
        a1 = client1.RegisterTopic('a',StringTopic)
        a2 = client1.RegisterTopic('a',StringTopic)
        b1 = client1.RegisterTopic('b',StringTopic)
        b2 = client1.RegisterTopic('b',StringTopic)
        a2.on_set += lambda x: b2.Set(x + " world")
        a1.Set("hello")
        time.sleep(0.1)
        self.assertEqual(b1.GetValue(), "hello world")

    def test_broadcast(self):
        port = get_free_port()
        server = ChatroomServer(port = port)
        sender = ChatroomClient(start=True,log_prefix="client1",port = port)
        recievers = [ChatroomClient(start=True,log_prefix=f"client{i}",port = port) for i in range(10)]
        server.RegisterTopic('a',StringTopic)
        a1 = sender.RegisterTopic('a',StringTopic)
        a = [r.RegisterTopic('a',StringTopic) for r in recievers]
        a1.Set("hello")
        time.sleep(0.1)
        for i in range(10):
            self.assertEqual(a[i].GetValue(), "hello")

    def test_reject(self):
        port = get_free_port()
        server = ChatroomServer(port = port)
        sender = ChatroomClient(start=True,log_prefix="sender",port = port)
        reciever = ChatroomClient(start=True,log_prefix="reciever",port = port)
        server_topic = server.RegisterTopic('a',StringTopic)
        sender_topic = sender.RegisterTopic('a',StringTopic)
        reciever_topic = reciever.RegisterTopic('a',StringTopic)

        server_topic.AddValidator(lambda *args,**kwargs: False)
        time.sleep(0.1)
        sender_topic.Set("hello")
        time.sleep(0.1)
        self.assertEqual(reciever_topic.GetValue(), '')
        self.assertEqual(sender_topic.GetValue(), '')

    def test_conditonal_reject(self):
        port = get_free_port()
        server = ChatroomServer(port = port)
        sender = ChatroomClient(start=True,log_prefix="sender",port = port)
        reciever = ChatroomClient(start=True,log_prefix="reciever",port = port)

        sender_topic = sender.RegisterTopic('guess_a_number',StringTopic)
        reciever_topic = reciever.RegisterTopic('guess_a_number',StringTopic)
        server_topic = server.RegisterTopic('guess_a_number',StringTopic)

        def validate_change(old_value,new_value,change):
            # only accept numbers between 0 and 100
            if int(change.value) > 100:
                return False
            elif int(change.value) < 0:
                return False
            else:
                return True
            
        server_topic.AddValidator(validate_change)
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

class TestTopicChanges(unittest.TestCase):
    def test_u_list(self):
        port = get_free_port()
        server = ChatroomServer(port = port)
        client1 = ChatroomClient(start=True,log_prefix="client1",port = port)
        client2 = ChatroomClient(start=True,log_prefix="client2",port = port)

        control = []
        set1 = client1.RegisterTopic('set',SetTopic)
        set2 = client2.RegisterTopic('set',SetTopic)

        app1 = Empty(a=[],b=[])
        app2 = Empty(a=[],b=[])

        # on_set
        def set1_set(x): app1.a = x
        def set2_set(x): app2.a = x
        set1.on_set += set1_set
        set2.on_set += set2_set

        # on_add and on_remove
        set1.on_append += lambda x: app1.b.append(x)
        set1.on_remove += lambda x: app1.b.remove(x)
        set2.on_append += lambda x: app2.b.append(x)
        set2.on_remove += lambda x: app2.b.remove(x)

        def assert_equal(answer):
            answer = sorted(map(json.dumps,answer))
            self.assertEqual(sorted(map(json.dumps,app1.a)), answer)
            self.assertEqual(sorted(map(json.dumps,app2.a)), answer)
            self.assertEqual(sorted(map(json.dumps,app1.b)), answer)
            self.assertEqual(sorted(map(json.dumps,app2.b)), answer)

        set1.Set([1,2,3])
        time.sleep(0.1)
        assert_equal([1,2,3])

        set1.Append({'a':1,'b':[{'c':100.1}]})
        set2.Append(5)
        time.sleep(0.1)
        assert_equal([1,2,3,{'a':1,'b':[{'c':100.1}]},5])

        set1.Remove(1)
        set2.Remove(2)
        set2.Append(6)
        set1.Remove(3)
        time.sleep(0.1)
        assert_equal([{'a':1,'b':[{'c':100.1}]},5,6])

        set2.Set([5,6,7])
        time.sleep(0.1)
        assert_equal([5,6,7])

