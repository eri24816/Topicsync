from contextlib import suppress
import unittest
from chatroom.state_machine.state_machine import StateMachine
from chatroom.topic import StringTopic
from chatroom.topic_change import InvalidChangeError

class StateMachineTransition(unittest.TestCase):
    def test_simple_transition(self):
        changes_list = []
        transition_list = []
        machine = StateMachine(on_changes_made=lambda changes,_:changes_list.append(changes),on_transition_done=lambda transition: transition_list.append(transition))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        with machine.record():
            a.Set('hello')
            b.Set('world')
            a.Set('hello2')
        self.assertEqual(a.get_value(),'hello2')
        self.assertEqual(b.get_value(),'world')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),['a','b','a'])

    def test_chain(self):
        changes_list = []
        transition_list = []
        machine = StateMachine(on_changes_made=lambda changes,_:changes_list.append(changes),on_transition_done=lambda transition: transition_list.append(transition))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        a.on_set += lambda value: b.Set('hello '+value)
        b.on_set += lambda value: c.Set(value+'!')
        with machine.record():
            a.Set('world')
        self.assertEqual(a.get_value(),'world')
        self.assertEqual(b.get_value(),'hello world')
        self.assertEqual(c.get_value(),'hello world!')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),['a','b','c'])

    def test_failed_transition(self):
        changes_list = []
        transition_list = []
        machine = StateMachine(on_changes_made=lambda changes,_:changes_list.append(changes),on_transition_done=lambda transition: transition_list.append(transition))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        a.on_set += lambda value: b.Set('hello '+value)
        b.on_set += lambda value: c.Set(value+'!')
        b.add_validator(lambda old,new,change: new != 'hello world')
        with self.assertRaises(InvalidChangeError):
            with machine.record():
                a.Set('world')
        self.assertEqual(a.get_value(),'')
        self.assertEqual(b.get_value(),'')
        self.assertEqual(c.get_value(),'')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),[])

        with machine.record():
            a.Set('Eric')

        self.assertEqual(a.get_value(),'Eric')
        self.assertEqual(b.get_value(),'hello Eric')
        self.assertEqual(c.get_value(),'hello Eric!')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[1])),['a','b','c'])

    def test_failed_and_catched_tranition(self):
        changes_list = []
        transition_list = []
        machine = StateMachine(on_changes_made=lambda changes,_:changes_list.append(changes),on_transition_done=lambda transition: transition_list.append(transition))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        a.on_set += lambda value: b.Set('hello '+value)
        b.on_set += lambda value: c.Set(value+'!')
        b.add_validator(lambda old,new,change: new != 'hello world')
        with machine.record():
            try:
                a.Set('world')
            except InvalidChangeError:
                pass
        self.assertEqual(a.get_value(),'')
        self.assertEqual(b.get_value(),'')
        self.assertEqual(c.get_value(),'')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),[])
        
        with machine.record():
            a.Set('Eric')
        
        self.assertEqual(a.get_value(),'Eric')
        self.assertEqual(b.get_value(),'hello Eric')
        self.assertEqual(c.get_value(),'hello Eric!')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[1])),['a','b','c'])
    
    def test_prevent_recursive_change(self):
        changes_list = []
        transition_list = []
        machine = StateMachine(on_changes_made=lambda changes,_:changes_list.append(changes),on_transition_done=lambda transition: transition_list.append(transition))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        a.on_set += lambda value: b.Set('hello '+value)
        b.on_set += lambda value: c.Set(value+'!')
        c.on_set += lambda value: a.Set('NO ' + value)
        with machine.record():
            a.Set('world')

        self.assertEqual(a.get_value(),'world')
        self.assertEqual(b.get_value(),'hello world')
        self.assertEqual(c.get_value(),'hello world!')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),['a', 'b', 'c'])

    def test_fail_set_without_except(self):
        changes_list = []
        machine = StateMachine(on_changes_made=lambda changes,_:changes_list.append(changes))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        b.add_validator(lambda old,new,change: False)
        with self.assertRaises(InvalidChangeError):
            with machine.record():
                a.Set('world')
                b.Set('test')
        
        self.assertEqual(a.get_value(), '')
        self.assertEqual(b.get_value(), '')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),[])

    def test_fail_set_with_except(self):
        changes_list = []
        machine = StateMachine(on_changes_made=lambda changes,_:changes_list.append(changes))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        b.add_validator(lambda old,new,change: new != 'test')
        with machine.record():
            a.Set('hello')
            try:
                b.Set('test')
            except:
                b.Set('test1')
            c.Set('world')
        
        self.assertEqual(a.get_value(), 'hello')
        self.assertEqual(b.get_value(), 'test1')
        self.assertEqual(c.get_value(), 'world')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),['a', 'b', 'c'])

    def test_try_except_in_on_set(self):
        changes_list = []
        machine = StateMachine(on_changes_made=lambda changes,_:changes_list.append(changes))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        c.add_validator(lambda old,new,change: False)
        a.on_set += lambda value: b.Set(value + ' world')

        def try_on_set(value):
            try:
                c.Set('invalid')
            except:
                pass 

        b.on_set += try_on_set

        with machine.record():
            a.Set('hello')
        
        self.assertEqual(a.get_value(), 'hello')
        self.assertEqual(b.get_value(), 'hello world')
        self.assertEqual(c.get_value(), '')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),['a', 'b'])

    def test_fail_subtrees(self):
        changes_list = []
        machine = StateMachine(on_changes_made=lambda changes,_:changes_list.append(changes))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        d=machine.add_topic('d',StringTopic)
        e=machine.add_topic('e',StringTopic)

        a.on_set += lambda value: d.Set('newd')
        a.on_set += lambda value: b.Set('newb')
        b.on_set += lambda value: c.Set('newc')
        c.add_validator(lambda old,new,change: False)
        d.on_set += lambda value: e.Set('newe')
        with machine.record():
            try:
                a.Set('hello')
            except:
                pass
        
        self.assertEqual(a.get_value(), '')
        self.assertEqual(b.get_value(), '')
        self.assertEqual(c.get_value(), '')
        self.assertEqual(d.get_value(), '')
        self.assertEqual(e.get_value(), '')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),[])