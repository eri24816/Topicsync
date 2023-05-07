import unittest
from chatroom.state_machine import StateMachine
from chatroom.topic import EventTopic, StringTopic

# class StateMachineTransition(unittest.TestCase):
#     def test_simple_transition(self):
#         changes_list = []
#         transition_list = []
#         machine = StateMachine(on_changes_made=lambda changes,_:changes_list.append(changes),on_transition_done=lambda transition: transition_list.append(transition))
#         a=machine.add_topic('a',StringTopic)
#         b=machine.add_topic('b',StringTopic)
#         with machine.record():
#             a.set('hello')
#             b.set('world')
#             a.set('hello2')
#         self.assertEqual(a.get(),'hello2')
#         self.assertEqual(b.get(),'world')
#         self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),['a','b','a'])

class Test(unittest.TestCase):
    def test_simple_transition(self):
        changes_list = []
        transition_list = []
        machine = StateMachine(on_changes_made=lambda changes,_:changes_list.append(changes),on_transition_done=lambda transition: transition_list.append(transition))
        a=machine.add_topic('a',StringTopic)
        b=machine.add_topic('b',StringTopic)
        e=machine.add_topic('e',EventTopic)
        e.on_emit += lambda: a.set('hello')
        a.on_set += lambda value: b.set(value+' world')
        with machine.record():
            e.emit()
        self.assertEqual(a.get(),'hello')
        self.assertEqual(b.get(),'hello world')

        self.assertEqual(list(map(lambda change: change.topic_name,changes_list[0])),['a','b'])