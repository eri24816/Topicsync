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