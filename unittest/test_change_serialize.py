import unittest
from chatroom.change import *


# Test serialize/deserialize of concrete changes
class TestChangeSerialize(unittest.TestCase):
    def test_null_change_exception(self):
        change = NullChange('topic')
        with self.assertRaises(NotImplementedError):
            change.serialize()

    def _test_serializable(self, change):
        serialized = change.serialize()
        restored = Change.deserialize(serialized)
        self.assertEqual(change, restored)

    def test_generic_set(self):
        change = GenericChangeTypes.SetChange('topic', 0, 1)
        self._test_serializable(change)

    def test_string_set(self):
        change = StringChangeTypes.SetChange('topic', 'val', 'oval')
        self._test_serializable(change)

    def test_int_set(self):
        change = IntChangeTypes.SetChange('topic', 0, 1)
        self._test_serializable(change)

    def test_int_add(self):
        change = IntChangeTypes.AddChange('topic', 10)
        self._test_serializable(change)

    def test_float_set(self):
        change = FloatChangeTypes.SetChange('topic', 0.5, 0.8)
        self._test_serializable(change)

    def test_float_add(self):
        change = FloatChangeTypes.AddChange('topic', 0.2)
        self._test_serializable(change)
        
    def test_set_set(self):
        change = SetChangeTypes.SetChange('topic', [1, 2], [1])
        self._test_serializable(change)
        
    def test_set_append(self):
        change = SetChangeTypes.AppendChange('topic', 4)
        self._test_serializable(change)
        
    def test_set_remove(self):
        change = SetChangeTypes.RemoveChange('topic', 10)
        self._test_serializable(change)
        
    def test_list_set(self):
        change = ListChangeTypes.SetChange('topic', [1], [])
        self._test_serializable(change)
        
    def test_list_insert(self):
        change = ListChangeTypes.InsertChange('topic', 4, 10)
        self._test_serializable(change)
    
    def test_list_pop(self):
        change = ListChangeTypes.PopChange('topic', 3)
        self._test_serializable(change)
        
    def test_dict_set(self):
        change = DictChangeTypes.SetChange('topic', {'a': 3, 'b': 10}, {})
        self._test_serializable(change)
        
    def test_dict_add(self):
        change = DictChangeTypes.AddChange('topic', 'k', 'v')
        self._test_serializable(change)
        
    def test_dict_remove(self):
        change = DictChangeTypes.RemoveChange('topic', 'k')
        self._test_serializable(change)
        
    def test_dict_change_value(self):
        change = DictChangeTypes.ChangeValueChange('topic', 'k', 'v10', 'v')
        self._test_serializable(change)

    def test_event_emit(self):
        change = EventChangeTypes.EmitChange('topic', {'arg1': 0, 'arg2': 10.0}, {'f1': '1', 'f2': 10})
        self._test_serializable(change)

    def test_event_reversed_emit(self):
        change = EventChangeTypes.ReversedEmitChange('topic', {'arg1': 5}, {'f2': 1})
        self._test_serializable(change)

    def test_binary_set(self):
        change = BinaryChangeTypes.SetChange('topic', 'bbb', '')
        self._test_serializable(change)