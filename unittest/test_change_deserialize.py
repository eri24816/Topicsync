import unittest
from topicsync.change import *


# Test deserialize of concrete changes
# NullChange and EventChangeTypes.* are omitted, since they are never (and shouldn't) created by deserializing
class TestChangeDeserialize(unittest.TestCase):

    def _test_deserializable(self, change):
        serialized = change.serialize()
        restored = Change.deserialize(serialized)
        self.assertEqual(change, restored)

    def test_generic_set(self):
        change = GenericChangeTypes.SetChange('topic', 0, 1)
        self._test_deserializable(change)

    def test_string_insert(self):
        change = StringChangeTypes.InsertChange('topic', 'v1', 10, 'abc')
        self._test_deserializable(change)

    def test_string_delete(self):
        change = StringChangeTypes.DeleteChange('topic', 'v1', 1, 'cc')
        self._test_deserializable(change)

    def test_string_set(self):
        change = StringChangeTypes.SetChange('topic', 'val', 'oval')
        self._test_deserializable(change)

    def test_int_set(self):
        change = IntChangeTypes.SetChange('topic', 0, 1)
        self._test_deserializable(change)

    def test_int_add(self):
        change = IntChangeTypes.AddChange('topic', 10)
        self._test_deserializable(change)

    def test_float_set(self):
        change = FloatChangeTypes.SetChange('topic', 0.5, 0.8)
        self._test_deserializable(change)

    def test_float_add(self):
        change = FloatChangeTypes.AddChange('topic', 0.2)
        self._test_deserializable(change)
        
    def test_set_set(self):
        change = SetChangeTypes.SetChange('topic', [1, 2], [1])
        self._test_deserializable(change)
        
    def test_set_append(self):
        change = SetChangeTypes.AppendChange('topic', 4)
        self._test_deserializable(change)
        
    def test_set_remove(self):
        change = SetChangeTypes.RemoveChange('topic', 10)
        self._test_deserializable(change)
        
    def test_list_set(self):
        change = ListChangeTypes.SetChange('topic', [1], [])
        self._test_deserializable(change)
        
    def test_list_insert(self):
        change = ListChangeTypes.InsertChange('topic', 4, 10)
        self._test_deserializable(change)
    
    def test_list_pop(self):
        change = ListChangeTypes.PopChange('topic', 3)
        self._test_deserializable(change)
        
    def test_dict_set(self):
        change = DictChangeTypes.SetChange('topic', {'a': 3, 'b': 10}, {})
        self._test_deserializable(change)
        
    def test_dict_add(self):
        change = DictChangeTypes.AddChange('topic', 'k', 'v')
        self._test_deserializable(change)
        
    def test_dict_remove(self):
        change = DictChangeTypes.PopChange('topic', 'k')
        self._test_deserializable(change)
        
    def test_dict_change_value(self):
        change = DictChangeTypes.ChangeValueChange('topic', 'k', 'v10', 'v')
        self._test_deserializable(change)