import unittest
from chatroom.state_machine import StateMachine
from chatroom.topic import StringTopic
from chatroom.change import InvalidChangeError

class StateMachineTransition(unittest.TestCase):
    def test_simple_transition(self):
        changes_list = []
        transition_list = []
        machine = StateMachine(on_changes_made=lambda changes,_:changes_list.append(changes),on_transition_done=lambda transition: transition_list.append(transition))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        with machine.record():
            a.set('hello')
            b.set('world')
            a.set('hello2')
        self.assertEqual(a.get(),'hello2')
        self.assertEqual(b.get(),'world')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),['a','b','a'])

    def test_chain(self):
        changes_list = []
        transition_list = []
        machine = StateMachine(on_changes_made=lambda changes,_:changes_list.append(changes),on_transition_done=lambda transition: transition_list.append(transition))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        a.on_set += lambda value: b.set('hello '+value)
        b.on_set += lambda value: c.set(value+'!')
        with machine.record():
            a.set('world')
        self.assertEqual(a.get(),'world')
        self.assertEqual(b.get(),'hello world')
        self.assertEqual(c.get(),'hello world!')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),['a','b','c'])

    def test_failed_transition(self):
        changes_list = []
        transition_list = []
        machine = StateMachine(on_changes_made=lambda changes,_:changes_list.append(changes),on_transition_done=lambda transition: transition_list.append(transition))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        a.on_set += lambda value: b.set('hello '+value)
        b.on_set += lambda value: c.set(value+'!')
        b.add_validator(lambda old,new,change: new != 'hello world')
        with self.assertRaises(InvalidChangeError):
            with machine.record():
                a.set('world')
        self.assertEqual(a.get(),'')
        self.assertEqual(b.get(),'')
        self.assertEqual(c.get(),'')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),[])

        with machine.record():
            a.set('Eric')

        self.assertEqual(a.get(),'Eric')
        self.assertEqual(b.get(),'hello Eric')
        self.assertEqual(c.get(),'hello Eric!')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[1])),['a','b','c'])

    def test_failed_and_catched_tranition(self):
        changes_list = []
        transition_list = []
        machine = StateMachine(on_changes_made=lambda changes,_:changes_list.append(changes),on_transition_done=lambda transition: transition_list.append(transition))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        a.on_set += lambda value: b.set('hello '+value)
        b.on_set += lambda value: c.set(value+'!')
        b.add_validator(lambda old,new,change: new != 'hello world')
        with machine.record():
            try:
                a.set('world')
            except InvalidChangeError:
                pass
        self.assertEqual(a.get(),'')
        self.assertEqual(b.get(),'')
        self.assertEqual(c.get(),'')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),[])
        
        with machine.record():
            a.set('Eric')
        
        self.assertEqual(a.get(),'Eric')
        self.assertEqual(b.get(),'hello Eric')
        self.assertEqual(c.get(),'hello Eric!')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[1])),['a','b','c'])
    
    def test_prevent_recursive_change(self):
        changes_list = []
        transition_list = []
        machine = StateMachine(on_changes_made=lambda changes,_:changes_list.append(changes),on_transition_done=lambda transition: transition_list.append(transition))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        a.on_set += lambda value: b.set('hello '+value)
        b.on_set += lambda value: c.set(value+'!')
        c.on_set += lambda value: a.set('NO ' + value)
        with machine.record():
            a.set('world')

        self.assertEqual(a.get(),'world')
        self.assertEqual(b.get(),'hello world')
        self.assertEqual(c.get(),'hello world!')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),['a', 'b', 'c'])

    def test_fail_set_without_except(self):
        changes_list = []
        machine = StateMachine(on_changes_made=lambda changes,_:changes_list.append(changes))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        b.add_validator(lambda old,new,change: False)
        with self.assertRaises(InvalidChangeError):
            with machine.record():
                a.set('world')
                b.set('test')
        
        self.assertEqual(a.get(), '')
        self.assertEqual(b.get(), '')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),[])

    def test_fail_set_with_except(self):
        changes_list = []
        machine = StateMachine(on_changes_made=lambda changes,_:changes_list.append(changes))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        b.add_validator(lambda old,new,change: new != 'test')
        with machine.record():
            a.set('hello')
            try:
                b.set('test')
            except:
                b.set('test1')
            c.set('world')
        
        self.assertEqual(a.get(), 'hello')
        self.assertEqual(b.get(), 'test1')
        self.assertEqual(c.get(), 'world')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),['a', 'b', 'c'])

    def test_try_except_in_on_set(self):
        changes_list = []
        machine = StateMachine(on_changes_made=lambda changes,_:changes_list.append(changes))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        c.add_validator(lambda old,new,change: False)
        a.on_set += lambda value: b.set(value + ' world')

        def try_on_set(value):
            try:
                c.set('invalid')
            except:
                pass 

        b.on_set += try_on_set

        with machine.record():
            a.set('hello')
        
        self.assertEqual(a.get(), 'hello')
        self.assertEqual(b.get(), 'hello world')
        self.assertEqual(c.get(), '')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),['a', 'b'])

    def test_fail_subtrees(self):
        changes_list = []
        machine = StateMachine(on_changes_made=lambda changes,_:changes_list.append(changes))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        d=machine.add_topic('d',StringTopic)
        e=machine.add_topic('e',StringTopic)

        a.on_set += lambda value: d.set('newd')
        a.on_set += lambda value: b.set('newb')
        b.on_set += lambda value: c.set('newc')
        c.add_validator(lambda old,new,change: False)
        d.on_set += lambda value: e.set('newe')
        with machine.record():
            try:
                a.set('hello')
            except:
                pass
        
        self.assertEqual(a.get(), '')
        self.assertEqual(b.get(), '')
        self.assertEqual(c.get(), '')
        self.assertEqual(d.get(), '')
        self.assertEqual(e.get(), '')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),[])

from chatroom import HistoryManager
class StateMachineUndoRedo(unittest.TestCase):
    def test_undo_redo(self):
        history = HistoryManager()
        machine = StateMachine(on_transition_done=history.add_transition)
        history.set_server(machine)

        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        a.on_set += lambda value: b.set('hello '+value)
        b.on_set += lambda value: c.set(value+'!')
        a.set('world')
        b.set('uwu')
        c.set('owo')

        self.assertEqual(a.get(),'world')
        self.assertEqual(b.get(),'uwu')
        self.assertEqual(c.get(),'owo')
        
        history.undo()
        self.assertEqual(a.get(),'world')
        self.assertEqual(b.get(),'uwu')
        self.assertEqual(c.get(),'uwu!')

        history.undo()
        self.assertEqual(a.get(),'world')
        self.assertEqual(b.get(),'hello world')
        self.assertEqual(c.get(),'hello world!')

        history.undo()
        self.assertEqual(a.get(),'')
        self.assertEqual(b.get(),'')
        self.assertEqual(c.get(),'')

        history.redo()
        self.assertEqual(a.get(),'world')
        self.assertEqual(b.get(),'hello world')
        self.assertEqual(c.get(),'hello world!')

        history.redo()
        self.assertEqual(a.get(),'world')
        self.assertEqual(b.get(),'uwu')
        self.assertEqual(c.get(),'uwu!')

        history.redo()
        self.assertEqual(a.get(),'world')
        self.assertEqual(b.get(),'uwu')
        self.assertEqual(c.get(),'owo')

    def test_undo_redo_2(self):
        history = HistoryManager()
        machine = StateMachine(on_transition_done=history.add_transition)
        history.set_server(machine)

        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        a.on_set += lambda value: b.set('hello '+value)
        b.on_set += lambda value: c.set(value+'!')
        with machine.record():
            a.set('world')
            b.set('uwu')

        with machine.record():
            c.set('owo')
            a.set('chatroom')

        self.assertEqual(a.get(),'chatroom')
        self.assertEqual(b.get(),'hello chatroom')
        self.assertEqual(c.get(),'hello chatroom!')

        history.undo()
        self.assertEqual(a.get(),'world')
        self.assertEqual(b.get(),'uwu')
        self.assertEqual(c.get(),'uwu!')

        history.undo()
        self.assertEqual(a.get(),'')
        self.assertEqual(b.get(),'')
        self.assertEqual(c.get(),'')

        history.redo()
        self.assertEqual(a.get(),'world')
        self.assertEqual(b.get(),'uwu')
        self.assertEqual(c.get(),'uwu!')

        history.redo()
        self.assertEqual(a.get(),'chatroom')
        self.assertEqual(b.get(),'hello chatroom')
        self.assertEqual(c.get(),'hello chatroom!')