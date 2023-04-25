from chatroom.server.server import ChatroomServer
from chatroom.state_machine import StateMachine, Transition


class HistoryManager:
    '''
    A simple history manager that stores transitions and a pointer to the current transition
    '''
    def __init__(self):
        self._history = []
        self._current_ptr = -1
    
    def set_server(self,chatroom:ChatroomServer|StateMachine):
        self._chatroom = chatroom

    def add_transition(self,transition:Transition):
        self._current_ptr += 1
        self._history = self._history[:self._current_ptr]
        self._history.append(transition)
        
    def undo(self):
        if len(self._history) > 0:
            self._chatroom.undo(self._history[self._current_ptr])
            self._current_ptr -= 1

    def redo(self):
        if self._current_ptr < len(self._history)-1:
            self._current_ptr += 1
            self._chatroom.redo(self._history[self._current_ptr])
