import unittest
from topicsync.state_machine import state_machine
from topicsync.state_machine.state_machine import StateMachine
from topicsync.topic import EventTopic, StringTopic
from topicsync.change import InvalidChangeError

class StateMachineTransition(unittest.TestCase):
    def test_simple_transition(self):
        changes_list = []
        transition_list = []
        machine = StateMachine(changes_callback=lambda changes,_:changes_list.append(changes),transition_callback=lambda transition: transition_list.append(transition))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        with machine.record():
            a.set('hello')
            b.set('world')
            a.set('hello2')
        self.assertEqual(a.get(),'hello2')
        self.assertEqual(b.get(),'world')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[-1])),['a','b','a'])

    def test_chain(self):
        changes_list = []
        transition_list = []
        machine = StateMachine(changes_callback=lambda changes,_:changes_list.append(changes),transition_callback=lambda transition: transition_list.append(transition))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        a.on_set.add_auto(lambda value: b.set('hello '+value))
        b.on_set.add_auto(lambda value: c.set(value+'!'))
        with machine.record():
            a.set('world')
        self.assertEqual(a.get(),'world')
        self.assertEqual(b.get(),'hello world')
        self.assertEqual(c.get(),'hello world!')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[-1])),['a','b','c'])

    def test_failed_transition(self):
        changes_list = []
        transition_list = []
        machine = StateMachine(changes_callback=lambda changes,_:changes_list.append(changes),transition_callback=lambda transition: transition_list.append(transition))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        a.on_set.add_auto(lambda value: b.set('hello '+value))
        b.on_set.add_auto(lambda value: c.set(value+'!'))
        b.add_validator(lambda new,change: new != 'hello world')
        with self.assertRaises(InvalidChangeError):
            with machine.record():
                a.set('world')
        self.assertEqual(a.get(),'')
        self.assertEqual(b.get(),'')
        self.assertEqual(c.get(),'')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[-1])),['a','a'])

        with machine.record():
            a.set('Eric')

        self.assertEqual(a.get(),'Eric')
        self.assertEqual(b.get(),'hello Eric')
        self.assertEqual(c.get(),'hello Eric!')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[-1])),['a','b','c'])

    def test_failed_and_catched_tranition(self):
        changes_list = []
        transition_list = []
        machine = StateMachine(changes_callback=lambda changes,_:changes_list.append(changes),transition_callback=lambda transition: transition_list.append(transition))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        a.on_set.add_auto(lambda value: b.set('hello '+value))
        b.on_set.add_auto(lambda value: c.set(value+'!'))
        b.add_validator(lambda new,change: new != 'hello world')
        with machine.record():
            try:
                a.set('world')
            except InvalidChangeError:
                pass
        self.assertEqual(a.get(),'')
        self.assertEqual(b.get(),'')
        self.assertEqual(c.get(),'')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[-1])),['a','a'])
        
        with machine.record():
            a.set('Eric')
        
        self.assertEqual(a.get(),'Eric')
        self.assertEqual(b.get(),'hello Eric')
        self.assertEqual(c.get(),'hello Eric!')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[-1])),['a','b','c'])
    
    # test_prevent_recursive_change is removed because from v0.6.0, recursive changes are not blocked anymore.

    # def test_prevent_recursive_change(self):
    #     changes_list = []
    #     transition_list = []
    #     machine = StateMachine(changes_callback=lambda changes,_:changes_list.append(changes),transition_callback=lambda transition: transition_list.append(transition))
    #     a=machine.add_topic('a',StringTopic)
    #     b=machine.add_topic('b',StringTopic)
    #     c=machine.add_topic('c',StringTopic)
    #     a.on_set.add_auto(lambda value: b.set('hello '+value))
    #     b.on_set.add_auto(lambda value: c.set(value+'!'))
    #     c.on_set.add_auto(lambda value: a.set('NO ' + value))
    #     with machine.record():
    #         a.set('world')

    #     self.assertEqual(a.get(),'world')
    #     self.assertEqual(b.get(),'hello world')
    #     self.assertEqual(c.get(),'hello world!')
    #     self.assertEqual(list(map(lambda change: change.topic_name,changes_list[-1])),['a', 'b', 'c'])

    def test_fail_set_without_except(self):
        changes_list = []
        machine = StateMachine(changes_callback=lambda changes,_:changes_list.append(changes))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        b.add_validator(lambda new,change: False)
        with self.assertRaises(InvalidChangeError):
            with machine.record():
                a.set('world')
                b.set('test')
        
        self.assertEqual(a.get(), '')
        self.assertEqual(b.get(), '')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[-1])),['a', 'a'])

    def test_fail_set_with_except(self):
        changes_list = []
        machine = StateMachine(changes_callback=lambda changes,_:changes_list.append(changes))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        b.add_validator(lambda new,change: new != 'test')
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
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[-1])),['a', 'b', 'c'])

    def test_try_except_in_on_set(self):
        changes_list = []
        machine = StateMachine(changes_callback=lambda changes,_:changes_list.append(changes))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        c.add_validator(lambda new,change: False)
        a.on_set.add_auto(lambda value: b.set(value + ' world'))

        def try_on_set(value):
            try:
                c.set('invalid')
            except:
                pass 

        b.on_set.add_auto(try_on_set)

        with machine.record():
            a.set('hello')
        
        self.assertEqual(a.get(), 'hello')
        self.assertEqual(b.get(), 'hello world')
        self.assertEqual(c.get(), '')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[-1])),['a', 'b'])

    def test_fail_subtrees(self):
        changes_list = []
        machine = StateMachine(changes_callback=lambda changes,_:changes_list.append(changes))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        d=machine.add_topic('d',StringTopic)
        e=machine.add_topic('e',StringTopic)

        a.on_set.add_auto(lambda value: d.set('newd'))
        a.on_set.add_auto(lambda value: b.set('newb'))
        b.on_set.add_auto(lambda value: c.set('newc'))
        c.add_validator(lambda new,change: False)
        d.on_set.add_auto(lambda value: e.set('newe'))
        with machine.record():
            try:
                a.set('newa')
            except:
                pass
        
        self.assertEqual(a.get(), '')
        self.assertEqual(b.get(), '')
        self.assertEqual(c.get(), '')
        self.assertEqual(d.get(), '')
        self.assertEqual(e.get(), '')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[-1])),['a', 'd', 'e', 'b', 'b', 'e', 'd', 'a'])

    def test_fail_subtrees_2(self):
        changes_list = []
        machine = StateMachine(changes_callback=lambda changes,_:changes_list.append(changes))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        d=machine.add_topic('d',StringTopic)
        e=machine.add_topic('e',StringTopic)
    
        a.on_set.add_auto(lambda value: d.set('newd'))
        a.on_set.add_auto(lambda value: b.set('newb'))

        def b_on_set(value):
            try:
                c.set('newc')
            except:
                pass

        b.on_set.add_auto(b_on_set)
        c.add_validator(lambda new,change: False)
        d.on_set.add_auto(lambda value: e.set('newe'))
        
        with machine.record():
            a.set('newa')
        
        self.assertEqual(a.get(), 'newa')
        self.assertEqual(b.get(), 'newb')
        self.assertEqual(c.get(), '')
        self.assertEqual(d.get(), 'newd')
        self.assertEqual(e.get(), 'newe')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[-1])),['a', 'd', 'e', 'b'])

    def test_recreate_topic(self):
        changes_list = []
        machine = StateMachine(changes_callback=lambda changes,_:changes_list.append(changes))
        a=machine.add_topic('a',StringTopic)
    
        machine.remove_topic('a')
        a=machine.add_topic('a',StringTopic)

        a.set('newa')

        self.assertEqual(machine.get_topic('a'),a)
        self.assertEqual(a.get(), 'newa')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[-1])),['a'])

from topicsync import HistoryManager
class UndoRedo(unittest.TestCase):
    def test_undo_redo(self):
        history = HistoryManager()
        machine = StateMachine(transition_callback=history.add_transition)
        history.set_server(machine)

        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        a.on_set.add_auto(lambda value: b.set('hello '+value))
        b.on_set.add_auto(lambda value: c.set(value+'!'))
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
        machine = StateMachine(transition_callback=history.add_transition)
        history.set_server(machine)

        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        c=machine.add_topic('c',StringTopic)
        a.on_set.add_auto(lambda value: b.set('hello '+value))
        b.on_set.add_auto(lambda value: c.set(value+'!'))
        with machine.record():
            a.set('world')
            b.set('uwu')

        with machine.record():
            c.set('owo')
            a.set('topicsync')

        self.assertEqual(a.get(),'topicsync')
        self.assertEqual(b.get(),'hello topicsync')
        self.assertEqual(c.get(),'hello topicsync!')

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
        self.assertEqual(a.get(),'topicsync')
        self.assertEqual(b.get(),'hello topicsync')
        self.assertEqual(c.get(),'hello topicsync!')

class RunAfterTransition(unittest.TestCase):

    def test_run_after_transition(self):
        changes_list = []
        transition_list = []
        machine = StateMachine(changes_callback=lambda changes,_:changes_list.append(changes),transition_callback=lambda transition: transition_list.append(transition))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic,init_value=' world')
        e=machine.add_topic('e',EventTopic)

        c=machine.add_topic('c',StringTopic,init_value=' !')

        def on_emit(**kwargs):
            old = a.get()
            a.set('hello')
            return {'old':old} # This information is useful for reverse
            
        e.on_emit.add_auto(on_emit)
        e.on_reverse.add_auto(lambda old: (a.set(old),print('reverse',old))) # This is called when undoing.

        # Although the callback c.set is added before b.set, it will be called after b.set, in the next transition.
        a.on_set.add_auto(lambda value: machine.do_after_transition(lambda: c.set(value+' !')))
        a.on_set.add_auto(lambda value: b.set(value+' world'))

        with machine.record():
            e.emit()
        self.assertEqual(a.get(),'hello')
        self.assertEqual(b.get(),'hello world')
        self.assertEqual(c.get(),'hello !')

        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),['e','a','b'])
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[1])),['c'])

        print(transition_list[1].changes[0].serialize())
        machine.undo(transition_list[1])
        self.assertEqual(c.get(),' !')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[2])),['c'])

        machine.undo(transition_list[0])
        self.assertEqual(a.get(),'')
        self.assertEqual(b.get(),' world')
        self.assertEqual(c.get(),' !')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[3])),['b','a','e'])

        machine.redo(transition_list[0])
        self.assertEqual(a.get(),'hello')
        self.assertEqual(b.get(),'hello world')
        self.assertEqual(c.get(),' !')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[4])),['e','a','b'])

        machine.redo(transition_list[1])
        self.assertEqual(a.get(),'hello')
        self.assertEqual(b.get(),'hello world')
        self.assertEqual(c.get(),'hello !')
        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[5])),['c'])