from contextlib import suppress
import unittest
from chatroom.command import ChangeCommand
from chatroom.state_machine.state_machine import StateMachine
from chatroom.topic import StringTopic
from chatroom.topic_change import InvalidChangeException

class StateMachineTransition(unittest.TestCase):
    def test_simple_transition(self):
        changes_list = []
        transition_list = []
        machine = StateMachine(on_changes_made=lambda changes:changes_list.append(changes),on_transition_done=lambda transition: transition_list.append(transition))
        machine.AddTopic(a:=StringTopic('a',machine))
        machine.AddTopic(b:=StringTopic('b',machine))
        with machine.Record():
            a.Set('hello')
            b.Set('world')
            a.Set('hello2')
        self.assertEqual(a.GetValue(),'hello2')
        self.assertEqual(b.GetValue(),'world')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),['a','b','a'])

    def test_chain(self):
        changes_list = []
        transition_list = []
        machine = StateMachine(on_changes_made=lambda changes:changes_list.append(changes),on_transition_done=lambda transition: transition_list.append(transition))
        machine.AddTopic(a:=StringTopic('a',machine))
        machine.AddTopic(b:=StringTopic('b',machine))
        machine.AddTopic(c:=StringTopic('c',machine))
        a.on_set += lambda value: b.Set('hello '+value)
        b.on_set += lambda value: c.Set(value+'!')
        with machine.Record():
            a.Set('world')
        self.assertEqual(a.GetValue(),'world')
        self.assertEqual(b.GetValue(),'hello world')
        self.assertEqual(c.GetValue(),'hello world!')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),['a','b','c'])

    def test_failed_transition(self):
        changes_list = []
        transition_list = []
        machine = StateMachine(on_changes_made=lambda changes:changes_list.append(changes),on_transition_done=lambda transition: transition_list.append(transition))
        machine.AddTopic(a:=StringTopic('a',machine))
        machine.AddTopic(b:=StringTopic('b',machine))
        machine.AddTopic(c:=StringTopic('c',machine))
        a.on_set += lambda value: b.Set('hello '+value)
        b.on_set += lambda value: c.Set(value+'!')
        b.AddValidator(lambda old,new,change: new != 'hello world')
        with self.assertRaises(InvalidChangeException):
            with machine.Record():
                a.Set('world')
        self.assertEqual(a.GetValue(),'')
        self.assertEqual(b.GetValue(),'')
        self.assertEqual(c.GetValue(),'')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),[])

        with machine.Record():
            a.Set('Eric')

        self.assertEqual(a.GetValue(),'Eric')
        self.assertEqual(b.GetValue(),'hello Eric')
        self.assertEqual(c.GetValue(),'hello Eric!')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[1])),['a','b','c'])

    def test_failed_and_catched_tranition(self):
        changes_list = []
        transition_list = []
        machine = StateMachine(on_changes_made=lambda changes:changes_list.append(changes),on_transition_done=lambda transition: transition_list.append(transition))
        machine.AddTopic(a:=StringTopic('a',machine))
        machine.AddTopic(b:=StringTopic('b',machine))
        machine.AddTopic(c:=StringTopic('c',machine))
        a.on_set += lambda value: b.Set('hello '+value)
        b.on_set += lambda value: c.Set(value+'!')
        b.AddValidator(lambda old,new,change: new != 'hello world')
        with machine.Record():
            try:
                a.Set('world')
            except InvalidChangeException:
                pass
        self.assertEqual(a.GetValue(),'')
        self.assertEqual(b.GetValue(),'')
        self.assertEqual(c.GetValue(),'')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),[])
        
        with machine.Record():
            a.Set('Eric')
        
        self.assertEqual(a.GetValue(),'Eric')
        self.assertEqual(b.GetValue(),'hello Eric')
        self.assertEqual(c.GetValue(),'hello Eric!')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[1])),['a','b','c'])
    
    def test_prevent_recursive_change(self):
        changes_list = []
        transition_list = []
        machine = StateMachine(on_changes_made=lambda changes:changes_list.append(changes),on_transition_done=lambda transition: transition_list.append(transition))
        machine.AddTopic(a:=StringTopic('a',machine))
        machine.AddTopic(b:=StringTopic('b',machine))
        machine.AddTopic(c:=StringTopic('c',machine))
        a.on_set += lambda value: b.Set('hello '+value)
        b.on_set += lambda value: c.Set(value+'!')
        c.on_set += lambda value: a.Set('NO ' + value)
        with machine.Record():
            a.Set('world')

        self.assertEqual(a.GetValue(),'world')
        self.assertEqual(b.GetValue(),'hello world')
        self.assertEqual(c.GetValue(),'hello world!')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),['a', 'b', 'c'])

    def test_fail_set_without_except(self):
        changes_list = []
        machine = StateMachine(on_changes_made=lambda changes:changes_list.append(changes))
        machine.AddTopic(a:=StringTopic('a',machine))
        machine.AddTopic(b:=StringTopic('b',machine))
        b.AddValidator(lambda old,new,change: False)
        with self.assertRaises(InvalidChangeException):
            with machine.Record():
                a.Set('world')
                b.Set('test')
        
        self.assertEqual(a.GetValue(), '')
        self.assertEqual(b.GetValue(), '')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),[])

    def test_fail_set_with_except(self):
        changes_list = []
        machine = StateMachine(on_changes_made=lambda changes:changes_list.append(changes))
        machine.AddTopic(a:=StringTopic('a',machine))
        machine.AddTopic(b:=StringTopic('b',machine))
        machine.AddTopic(c:=StringTopic('c',machine))
        b.AddValidator(lambda old,new,change: new != 'test')
        with machine.Record():
            a.Set('hello')
            try:
                b.Set('test')
            except:
                b.Set('test1')
            c.Set('world')
        
        self.assertEqual(a.GetValue(), 'hello')
        self.assertEqual(b.GetValue(), 'test1')
        self.assertEqual(c.GetValue(), 'world')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),['a', 'b', 'c'])

    def test_try_except_in_on_set(self):
        changes_list = []
        machine = StateMachine(on_changes_made=lambda changes:changes_list.append(changes))
        machine.AddTopic(a:=StringTopic('a',machine))
        machine.AddTopic(b:=StringTopic('b',machine))
        machine.AddTopic(c:=StringTopic('c',machine))
        c.AddValidator(lambda old,new,change: False)
        a.on_set += lambda value: b.Set(value + ' world')

        def try_on_set(value):
            try:
                c.Set('invalid')
            except:
                pass 

        b.on_set += try_on_set

        with machine.Record():
            a.Set('hello')
        
        self.assertEqual(a.GetValue(), 'hello')
        self.assertEqual(b.GetValue(), 'hello world')
        self.assertEqual(c.GetValue(), '')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),['a', 'b'])

    def test_fail_subtrees(self):
        changes_list = []
        machine = StateMachine(on_changes_made=lambda changes:changes_list.append(changes))
        machine.AddTopic(a:=StringTopic('a',machine))
        machine.AddTopic(b:=StringTopic('b',machine))
        machine.AddTopic(c:=StringTopic('c',machine))
        machine.AddTopic(d:=StringTopic('d',machine))
        machine.AddTopic(e:=StringTopic('e',machine))

        a.on_set += lambda value: d.Set('newd')
        a.on_set += lambda value: b.Set('newb')
        b.on_set += lambda value: c.Set('newc')
        c.AddValidator(lambda old,new,change: False)
        d.on_set += lambda value: e.Set('newe')
        with machine.Record():
            try:
                a.Set('hello')
            except:
                pass
        
        self.assertEqual(a.GetValue(), '')
        self.assertEqual(b.GetValue(), '')
        self.assertEqual(c.GetValue(), '')
        self.assertEqual(d.GetValue(), '')
        self.assertEqual(e.GetValue(), '')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),[])