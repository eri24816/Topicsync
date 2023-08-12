import unittest
from chatroom.topic import StringTopic
from chatroom.change import StringChangeTypes, InvalidChangeError, Change

from typing import Callable, Tuple

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

        assert topic.get() == 'ab'

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

    def test_delete_last_position_empty_string(self):
        topic = StringTopic('test', None, init_value='ddd')
        deletion = StringChangeTypes.DeleteChange('test', 3, '')

        topic.apply_change(deletion)

        assert topic.get() == 'ddd'

    def test_delete_last_position_nonempty_string(self):
        topic = StringTopic('test', None, init_value='ddd')
        deletion = StringChangeTypes.DeleteChange('test', 3, 'd')

        with self.assertRaises(InvalidChangeError):
            topic.apply_change(deletion, notify_listeners=False)


    def _test_2_change_order(self, result12, result21, topic_change_gen: Callable[[], Tuple[StringTopic, Change, Change]]):
        topic, change1, change2 = topic_change_gen()
        topic.apply_change(change1)
        topic.apply_change(change2)
        assert topic.get() == result12

        topic, change1, change2 = topic_change_gen()
        topic.apply_change(change2)
        topic.apply_change(change1)
        assert topic.get() == result21

    def test_multiple_insert(self):
        # the order of insertions on different position won't affect the result
        self._test_2_change_order(
            'axxxxbcyyyyd',
            'axxxxbcyyyyd',
            lambda: (topic := StringTopic('test', None, init_value='abcd'),
                     StringChangeTypes.InsertChange('test', topic.version, 1, 'xxxx'),
                     StringChangeTypes.InsertChange('test', topic.version, 3, 'yyyy'))
        )

    def test_multiple_insert_at_same_position(self):
        self._test_2_change_order(
            'ayyyyxxxxbcd',
            'axxxxyyyybcd',
            lambda: (topic := StringTopic('test', None, init_value='abcd'),
                     StringChangeTypes.InsertChange('test', topic.version, 1, 'xxxx'),
                     StringChangeTypes.InsertChange('test', topic.version, 1, 'yyyy'))
        )

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