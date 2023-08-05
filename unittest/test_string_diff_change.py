import unittest
from chatroom.topic import StringTopic
from chatroom.change import StringChangeTypes, InvalidChangeError

class TestStringDiffChange(unittest.TestCase):
    def test_insert_change(self):
        topic = StringTopic('test', None, init_value='ddd')
        insertion = StringChangeTypes.InsertChange('test', topic.version, 1, 'abcd')
        topic.apply_change(insertion, notify_listeners=False)

        assert topic.get() == 'dabcddd'

    def test_insert_position_greater_than_length(self):
        topic = StringTopic('test', None, init_value='ddd')
        insertion = StringChangeTypes.InsertChange('test', topic.version, 4, 'abcd')

        with self.assertRaises(InvalidChangeError):
            topic.apply_change(insertion, notify_listeners=False)

    def test_insert_position_less_than_zero(self):
        topic = StringTopic('test', None, init_value='ddd')
        insertion = StringChangeTypes.InsertChange('test', topic.version, -5, 'abcd')

        with self.assertRaises(InvalidChangeError):
            topic.apply_change(insertion, notify_listeners=False)

    def test_delete_change(self):
        topic = StringTopic('test', None, init_value='abcd')
        deletion = StringChangeTypes.DeleteChange('test', 2, 'cd')
        topic.apply_change(deletion)

    def test_delete_invalid_string(self):
        topic = StringTopic('test', None, init_value='abcd')
        deletion = StringChangeTypes.DeleteChange('test', 0, 'cd')
        with self.assertRaises(InvalidChangeError):
            topic.apply_change(deletion)

    def test_delete_position_greater_than_length(self):
        topic = StringTopic('test', None, init_value='ddd')
        deletion = StringChangeTypes.DeleteChange('test', 4, 'abcd')

        with self.assertRaises(InvalidChangeError):
            topic.apply_change(deletion, notify_listeners=False)

    def test_delete_position_less_than_zero(self):
        topic = StringTopic('test', None, init_value='ddd')
        deletion = StringChangeTypes.DeleteChange('test', -2, 'd')

        with self.assertRaises(InvalidChangeError):
            topic.apply_change(deletion, notify_listeners=False)

    def test_multiple_insert(self):
        topic = StringTopic('test', None, init_value='abcd')

        # imagine 2 cursors, insert at the same time
        ins1 = StringChangeTypes.InsertChange('test', topic.version, 1, 'xxxx')
        ins2 = StringChangeTypes.InsertChange('test', topic.version, 3, 'yyyy')
        topic.apply_change(ins1)
        topic.apply_change(ins2)

        assert topic.get() == 'axxxxbcyyyyd'

        topic = StringTopic('test', None, init_value='abcd')

        # the result should be the same even if the change is applied in a different order
        # because the changes are both made base on the string 'abcd'
        ins1 = StringChangeTypes.InsertChange('test', topic.version, 1, 'xxxx')
        ins2 = StringChangeTypes.InsertChange('test', topic.version, 3, 'yyyy')
        topic.apply_change(ins2)
        topic.apply_change(ins1)

        assert topic.get() == 'axxxxbcyyyyd'

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