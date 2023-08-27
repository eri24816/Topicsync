from __future__ import annotations
from dataclasses import dataclass

# cursor stands between characters, it doesn't directly refer to a character
# 0 is the first insertable position, right before the first character
# an observation to help thinking: the ith cursor positions before the ith character
def _before(string, cursor) -> str:
    return string[:cursor]

def _after(string, cursor) -> str:
    return string[cursor:]

def _valid_pos(string: str) -> range:
    return range(0, len(string) + 1)


def insert(old: str, pos: int, string: str) -> str:
    if pos not in _valid_pos(old):
        raise ValueError(f"Insertion invalid: invalid position {pos}. Insert position must between [0, len(old)]")

    return _before(old, pos) + string + _after(old, pos)


def delete(old: str, pos: int, string: str) -> str:
    if pos not in _valid_pos(old):
        raise ValueError(f'Deletion invalid: invalid position {pos}. Delete position must between [0, len(old)]')

    if not _after(old, pos).startswith(string):
        raise ValueError(f"Deletion invalid: string '{string}' doesn't appear at position {pos} of string '{old}'")

    return _before(old, pos) + _after(old, pos + len(string))


@dataclass
class _Range:
    start: int
    len: int
    start_base: int = 0

    def end(self) -> int:
        return self.start + self.len

    def relative_to(self, base) -> _Range:
        # its absolute position should be the same, that is, start_base + start is fixed
        return _Range(self.start_base + self.start - base, self.len, base)

    def is_overlapped_with(self, other: _Range) -> bool:
        if self.start <= other.start:
            return self.start + self.len > other.start
        # if self and other are overlapped, then other and self must overlap
        # if self starts after other, instead of writing same logic again, we swap 2 parameters
        return other.is_overlapped_with(self)

def _overlap_range(range1: _Range, range2: _Range) -> _Range:
    # absolute overlap range, only work when range1 and range2 has base 0, since it's the only use case
    if not range1.is_overlapped_with(range2):
        return _Range(0, 0)

    start = max(range1.start, range2.start)
    length = min(range1.end(), range2.end()) - start
    return _Range(start, length)

def adjust_delete(applied_start: int, applied_delete: str, current_start: int, current_delete: str) -> (int, str):
    delete1_range = _Range(applied_start, len(applied_delete))
    delete2_range = _Range(current_start, len(current_delete))

    if not delete1_range.is_overlapped_with(delete2_range):
        if applied_start < current_start:
            return current_start - delete1_range.len, current_delete
        else:
            return current_start, current_delete

    overlap_rel = _overlap_range(delete1_range, delete2_range).relative_to(delete2_range.start)

    return min(applied_start, current_start), \
        _before(current_delete, overlap_rel.start) + _after(current_delete, overlap_rel.end())

def extend_delete(deletion, at_pos: int, string: str) -> str:
    return _before(deletion, at_pos) + string + _after(deletion, at_pos)