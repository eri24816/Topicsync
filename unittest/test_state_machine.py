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

    def test_fail_transition_when_any_change_fail(self):
        changes_list = []
        transition_list = []
        machine = StateMachine(on_changes_made=lambda changes:changes_list.append(changes),on_transition_done=lambda transition: transition_list.append(transition))
        machine.AddTopic(a:=StringTopic('a',machine))
        machine.AddTopic(b:=StringTopic('b',machine))
        a.AddValidator(lambda old,new,change: new != 'world')
        with self.assertRaises(InvalidChangeException):
            with machine.Record():
                b.Set('Hi')
                a.Set('world')
        self.assertEqual(a.GetValue(),'')
        self.assertEqual(b.GetValue(),'')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),[])

        with machine.Record():
            b.Set('Hi')
            a.Set('Eric')
        
        self.assertEqual(a.GetValue(),'Eric')
        self.assertEqual(b.GetValue(),'Hi')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[1])),['b','a'])

    def test_error_when_changing_is_raised_outside(self):
        changes_list = []
        transition_list = []
        machine = StateMachine(on_changes_made=lambda changes:changes_list.append(changes),on_transition_done=lambda transition: transition_list.append(transition))
        machine.AddTopic(a:=StringTopic('a',machine))
        machine.AddTopic(b:=StringTopic('b',machine))
        machine.AddTopic(c:=StringTopic('c',machine))
        a.on_set += lambda value: b.Set('hello '+value)
        b.on_set += lambda value: c.Set(value+'!')
        b.AddValidator(lambda old,new,change: new != 'hello world')
        with self.assertRaises(InvalidChangeException) as cm:
            with machine.Record():
                try:
                    a.Set('world')
                except InvalidChangeException:
                    self.assertFalse(False, "Set shouldn't raise")
        # print(cm.exception)
        self.assertEqual(a.GetValue(),'')
        self.assertEqual(b.GetValue(),'')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),[])
        
        with machine.Record():
            a.Set('Eric')
        
        self.assertEqual(a.GetValue(),'Eric')
        self.assertEqual(b.GetValue(),'hello Eric')
        self.assertEqual(c.GetValue(),'hello Eric!')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[1])),['a','b','c'])