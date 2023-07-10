import unittest
from chatroom.topic import StringTopic
from chatroom.change import StringChangeTypes

class TestStringDiffChange(unittest.TestCase):
    def test_diff_change(self):
        topic = StringTopic('test', None, init_value='ddd')
        diff_change = StringChangeTypes.DiffChange(
            'test',
            inst=['iabcb', 'm1', 'd2']
        )
        topic.apply_change(diff_change, notify_listeners=False)

        assert topic.get() == 'abcbd'

    # def test_change_adjust(self):
    #     topic = StringTopic('test', None, init_value='')  # no need to use state machine
    #     topic.set()
    #     change1 = StringChangeTypes.SetChange('test', 'new_val')
    #     topic.apply_change(change1, False)
    #     assert topic.get() == 'new_val'
    #
    #     change2 = StringChangeTypes.InsertChange('test', insert={0: })
    #     change2.derive_version = change1.id
    #     topic.apply_change(change2)
    #     assert topic.get() == 'new_val2'