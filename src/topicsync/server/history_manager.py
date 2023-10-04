from topicsync.server.server import TopicsyncServer
from topicsync.state_machine.state_machine import StateMachine, Transition


class HistoryManager:
    '''
    A simple history manager that stores transitions and a pointer to the current transition
    '''
    def __init__(self):
        self._history = []
        self._current_ptr = -1
    
    def set_server(self,topicsync:TopicsyncServer|StateMachine):
        self._topicsync = topicsync

    def add_transition(self,transition:Transition):
        self._current_ptr += 1
        self._history = self._history[:self._current_ptr]
        self._history.append(transition)
        
    def undo(self):
        if len(self._history) > 0 and self._current_ptr >= 0:
            self._topicsync.undo(self._history[self._current_ptr])
            self._current_ptr -= 1

    def redo(self):
        if self._current_ptr < len(self._history)-1:
            self._current_ptr += 1
            self._topicsync.redo(self._history[self._current_ptr])
