import unittest
from chatroom.topic import StringTopic
from chatroom.change import StringChangeTypes, InvalidChangeError, Change

from typing import Callable, Tuple

class TestStringDiffChange(unittest.TestCase):
    def test_insert_change(self):
        topic = StringTopic('test', None, init_value='ddd')
        insertion = StringChangeTypes.InsertChange('test', topic.version, 1, 'abcd')
        topic.apply_change(insertion)

        assert topic.get() == 'dabcddd'

    def test_insert_position_greater_than_length(self):
        topic = StringTopic('test', None, init_value='ddd')
        insertion = StringChangeTypes.InsertChange('test', topic.version, 4, 'abcd')

        with self.assertRaises(InvalidChangeError):
            topic.apply_change(insertion)

    def test_insert_position_less_than_zero(self):
        topic = StringTopic('test', None, init_value='ddd')
        insertion = StringChangeTypes.InsertChange('test', topic.version, -5, 'abcd')

        with self.assertRaises(InvalidChangeError):
            topic.apply_change(insertion)

    def test_delete_change(self):
        topic = StringTopic('test', None, init_value='abcd')
        deletion = StringChangeTypes.DeleteChange('test', topic.version, 2, 'cd')
        topic.apply_change(deletion)

        assert topic.get() == 'ab'

    def test_delete_invalid_string(self):
        topic = StringTopic('test', None, init_value='abcd')
        deletion = StringChangeTypes.DeleteChange('test', topic.version, 0, 'cd')
        with self.assertRaises(InvalidChangeError):
            topic.apply_change(deletion)

    def test_delete_position_greater_than_length(self):
        topic = StringTopic('test', None, init_value='ddd')
        deletion = StringChangeTypes.DeleteChange('test', topic.version, 4, 'abcd')

        with self.assertRaises(InvalidChangeError):
            topic.apply_change(deletion)

    def test_delete_position_less_than_zero(self):
        topic = StringTopic('test', None, init_value='ddd')
        deletion = StringChangeTypes.DeleteChange('test', topic.version, -2, 'd')

        with self.assertRaises(InvalidChangeError):
            topic.apply_change(deletion)

    def test_delete_last_position_empty_string(self):
        topic = StringTopic('test', None, init_value='ddd')
        deletion = StringChangeTypes.DeleteChange('test', topic.version, 3, '')

        topic.apply_change(deletion)

        assert topic.get() == 'ddd'

    def test_delete_last_position_nonempty_string(self):
        topic = StringTopic('test', None, init_value='ddd')
        deletion = StringChangeTypes.DeleteChange('test', topic.version, 3, 'd')

        with self.assertRaises(InvalidChangeError):
            topic.apply_change(deletion)


    def _test_2_change_order(self, original, result12, result21, topic_change_gen: Callable[[str, str], Tuple[Change, Change]]):
        topic = StringTopic('test', None, init_value=original)
        change1, change2 = topic_change_gen(topic.get_name(), topic.version)
        topic.apply_change(change1)
        topic.apply_change(change2)
        assert topic.get() == result12

        topic = StringTopic('test', None, init_value=original)
        change1, change2 = topic_change_gen(topic.get_name(), topic.version)
        topic.apply_change(change2)
        topic.apply_change(change1)
        assert topic.get() == result21

    def test_2_insert(self):
        # the order of insertions on different position won't affect the result
        self._test_2_change_order(
            'abcd',
            'axxxxbcyyyyd',
            'axxxxbcyyyyd',
            lambda name, version: (
                 StringChangeTypes.InsertChange(name, version, 1, 'xxxx'),
                 StringChangeTypes.InsertChange(name, version, 3, 'yyyy')
            )
        )

    def test_2_insert_at_same_position(self):
        # when insertion happens, the cursor on the same position isn't moved.
        self._test_2_change_order(
            'abcd',
            'ayyyyxxxxbcd',
            'axxxxyyyybcd',
            lambda name, version: (
                 StringChangeTypes.InsertChange(name, version, 1, 'xxxx'),
                 StringChangeTypes.InsertChange(name, version, 1, 'yyyy')
            )
        )

    def test_2_delete_non_overlap(self):
        self._test_2_change_order(
            'ayyyyxxxxbcd',
            'abcd',
            'abcd',
            lambda name, version: (
                StringChangeTypes.DeleteChange(name, version, 1, 'yyyy'),
                StringChangeTypes.DeleteChange(name, version, 5, 'xxxx')
            )
        )

    def test_2_delete_same_pos(self):
        self._test_2_change_order(
            'ayyyyxxxxbcd',
            'abcd',
            'abcd',
            lambda name, version: (
                StringChangeTypes.DeleteChange(name, version, 1, 'yyyy'),
                StringChangeTypes.DeleteChange(name, version, 1, 'yyyyxxxx')
            )
        )

    def test_2_delete_identical(self):
        self._test_2_change_order(
            'ayyyyxxxxbcd',
            'abcd',
            'abcd',
            lambda name, version: (
                StringChangeTypes.DeleteChange(name, version, 1, 'yyyyxxxx'),
                StringChangeTypes.DeleteChange(name, version, 1, 'yyyyxxxx')
            )
        )

    def test_2_delete_overlap(self):
        self._test_2_change_order(
            'ayyyyxxxxbcd',
            'abcd',
            'abcd',
            lambda name, version: (
                StringChangeTypes.DeleteChange(name, version, 3, 'yyxxxx'),
                StringChangeTypes.DeleteChange(name, version, 1, 'yyyyx')
            )
        )

    def test_2_delete_subsequence(self):
        self._test_2_change_order(
            'ayyyyxxxxbcd',
            'abcd',
            'abcd',
            lambda name, version: (
                StringChangeTypes.DeleteChange(name, version, 1, 'yyyyxxxx'),
                StringChangeTypes.DeleteChange(name, version, 3, 'yyxx')
            )
        )

    def test_insert_then_delete_non_overlap(self):
        # insert happens at a position before delete range
        self._test_2_change_order(
            'axxxbcd',
            'ayyyybcd',
            'ayyyybcd',
            lambda name, version: (
                StringChangeTypes.InsertChange(name, version, 1, 'yyyy'),
                StringChangeTypes.DeleteChange(name, version, 1, 'xxx')
            )
        )

    def test_delete_then_insert_non_overlap(self):
        # insert happens at a position after delete range
        self._test_2_change_order(
            'axxxbcd',
            'ayyyybcd',
            'ayyyybcd',
            lambda name, version: (
                StringChangeTypes.InsertChange(name, version, 4, 'yyyy'),
                StringChangeTypes.DeleteChange(name, version, 1, 'xxx')
            )
        )

    def test_delete_insert_overlap(self):
        # the only possible overlap is when insertion happens in the range of a deletion
        self._test_2_change_order(
            'axxxbcd',
            'abcd',
            'abcd',
            lambda name, version: (
                StringChangeTypes.InsertChange(name, version, 2, 'yyyy'),
                StringChangeTypes.DeleteChange(name, version, 1, 'xxx')
            )
        )