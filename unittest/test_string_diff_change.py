import unittest
from chatroom.topic import StringTopic
from chatroom.change import StringChangeTypes

class TestStringDiffChange(unittest.TestCase):
    def test_insert_change(self):
        topic = StringTopic('test', None, init_value='ddd')
        insertion = StringChangeTypes.InsertChange('test', 1, 'abcd')
        topic.apply_change(insertion, notify_listeners=False)

        assert topic.get() == 'dabcddd'

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