import unittest
from chatroom.state_machine.state_machine import StateMachine
from chatroom.topic import StringTopic
from chatroom.change import StringChangeTypes

class MyTestCase(unittest.TestCase):
    '''
    Here we only test valid undo/redo
    '''
    def test_single_undo_redo_insert(self):
        transitions = []
        machine = StateMachine(transition_callback=transitions.append)
        topic = machine.add_topic('topic', StringTopic, init_value='a')

        with machine.record():
            topic.insert(1, 'bcde')
        assert topic.get() == 'abcde'
        assert len(transitions) == 1

        machine.undo(transitions[0])
        assert topic.get() == 'a'
        assert len(transitions) == 1

        machine.redo(transitions[0])
        assert topic.get() == 'abcde'
        assert len(transitions) == 1

    def test_single_undo_redo_delete(self):
        transitions = []
        machine = StateMachine(transition_callback=transitions.append)
        topic = machine.add_topic('topic', StringTopic, init_value='abcde')

        with machine.record():
            topic.delete(1, 'bcd')
        assert topic.get() == 'ae'
        assert len(transitions) == 1

        machine.undo(transitions[0])
        assert topic.get() == 'abcde'
        assert len(transitions) == 1

        machine.redo(transitions[0])
        assert topic.get() == 'ae'
        assert len(transitions) == 1

    def test_multiple_change_in_transition(self):
        transitions = []
        machine = StateMachine(transition_callback=transitions.append)
        topic = machine.add_topic('topic', StringTopic, init_value='abcde')

        with machine.record():
            topic.insert(2, 'xxx')
            topic.delete(1, 'bxx')
            topic.insert(3, 'yy')
        assert topic.get() == 'axcyyde'
        assert len(transitions) == 1

        machine.undo(transitions[0])
        assert topic.get() == 'abcde'
        assert len(transitions) == 1

        machine.redo(transitions[0])
        assert topic.get() == 'axcyyde'
        assert len(transitions) == 1