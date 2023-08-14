from __future__ import annotations
import enum
import logging

from chatroom.state_machine.changes_tree import ChangesTree, Tag
logger = logging.getLogger(__name__)
import threading
import traceback
from typing import TYPE_CHECKING, TypeVar
from contextlib import contextmanager, nullcontext
from typing import Any, Callable, List

from chatroom.change import EventChangeTypes, NullChange
from chatroom.topic import Topic, topic_factory
from chatroom.state_machine.transition_tree import TransitionTree
if TYPE_CHECKING:
    from chatroom.change import Change

class Transition:
    def __init__(self,changes:List[Change],action_source:int):
        self.changes = changes
        self.action_source = action_source

class Phase(enum.Enum):
    IDLE = 0
    FORWARDING = 1
    UNDOING = 2
    REDOING = 3



class StateMachine:
    def __init__(self, 
            changes_callback:Callable[[List[Change],str], None]=lambda *args:None, 
            transition_callback: Callable[[Transition], None]=lambda *args:None,
            changes_tree_callback: Callable[[ChangesTree], None]|None=None, 
            transition_tree_callback: Callable[[TransitionTree], None]|None=None
        ):

        self._phase: Phase = Phase.IDLE
        self._state : dict[str,Topic] = {}
        self._is_recording = False
        self._lock = threading.RLock()
        self._changes_list : List[Change] = []

        # Standard callbacks
        self._changes_callback = changes_callback
        self._transition_callback = transition_callback

        # Callbacks for debugging
        self._changes_tree_callback = changes_tree_callback
        self._transition_tree_callback = transition_tree_callback
        self._debug = changes_tree_callback is not None or transition_tree_callback is not None

        self._max_recursive_depth = 1e4
        self._apply_change_call_stack = []
        self._inside_emit_change = False
        self._transition_tree = None
        self._tasks_to_run_after_transition: List[Callable[[],None]] = []
    
    T = TypeVar('T', bound=Topic)
    def add_topic(self,name:str,topic_type:type[T],is_stateful:bool = True,init_value:Any=None)->T:
        topic = topic_type(name,self,is_stateful,init_value)
        self._state[name] = topic
        return topic
    
    def add_topic_s(self,name:str,topic_type:str,is_stateful:bool = True,init_value:Any=None)->Topic:
        topic = topic_factory(topic_type,name,self,is_stateful,init_value)
        self._state[name] = topic
        return topic
    
    def remove_topic(self,name:str):
        del self._state[name]

    def get_topic(self,topic_name:str)->Topic:
        return self._state[topic_name]
    
    def has_topic(self,topic_name:str):
        return topic_name in self._state

    @contextmanager
    def _block_recursion(self,max_depth:int = 0):
        self._max_recursive_depth = max_depth
        try:
            yield
        finally:
            self._max_recursive_depth = 1e4

    @contextmanager
    def record(self,action_source:int = 0,action_id:str = '',allow_reentry:bool = False,emit_transition:bool = True,phase:Phase = Phase.FORWARDING):
        #TODO: thread lock
        if self._is_recording:
            if not allow_reentry:
                raise RuntimeError("Cannot call record while already recording")
            else:
                # Already recording, just skip to yield
                yield
                return
            
        # Set up the recording

        with self._lock:

            self._is_recording = True
            self._phase = phase
            self._error_has_occured_in_transition = False
            self._changes_list = []
            self._transition_tree = TransitionTree(self.get_topic,self._changes_list)
            self._changes_tree = ChangesTree()
            try:
                yield
            except Exception:
                self._is_recording = False
                logger.warning("An error has occured in the transition. Cleaning up the failed transition. The error was:\n" + str(traceback.format_exc()))
                self._cleanup_failed_transition()
                raise
            else:
                self._is_recording = False
                current_transition = list(self._transition_tree.preorder_traversal(self._transition_tree.root))
                if len(current_transition) and emit_transition:
                    new_transition = Transition(current_transition,action_source)
                    self._transition_callback(new_transition)
            finally:
                self._is_recording = False
                self._phase = Phase.IDLE
                # discard NullChange, EmitChange, ReversedEmitChange
                self._changes_list = [
                    change for change in self._changes_list
                    if not isinstance(change,NullChange) and not isinstance(change,(EventChangeTypes.EmitChange,EventChangeTypes.ReversedEmitChange))]
                if len(self._changes_list):
                    self._changes_callback(self._changes_list,action_id)

                # debug

                if self._debug:
                    if self._changes_tree_callback is not None:
                        self._changes_tree_callback(self._changes_tree)
                    if self._transition_tree_callback is not None:
                        self._transition_tree_callback(self._transition_tree)

                # cleanup

                self._changes_list = []
                self._transition_tree = None

                for task in self._tasks_to_run_after_transition:
                    task()
                self._tasks_to_run_after_transition = []

        # unlock

    def _cleanup_failed_transition(self):
        try:
            with self._block_recursion():
                assert self._transition_tree.cursor.is_root
                self._transition_tree.clear_subtree()
        except Exception as e:
            logger.error("An error has occured while trying to undo the failed transition. The state is now in an inconsistent state. The error was: \n" +str(traceback.format_exc()))
            raise

    @contextmanager
    def _track_apply_change(self,topic_name):
        self._apply_change_call_stack.append(topic_name)
        try:
            yield
        finally:
            self._apply_change_call_stack.pop()

    @contextmanager
    def enter_emit_change(self):
        if self._inside_emit_change:
            yield 
            return
        self._inside_emit_change = True
        try:
            yield
        finally:
            self._inside_emit_change = False

    def apply_change(self,change:Change):
        
        with self._lock:

            topic = self.get_topic(change.topic_name)

            # Within self._block_recursion context, recursive depth for stateful topics is limited
            if topic.is_stateful() and (not self._inside_emit_change) and len(self._apply_change_call_stack)+1 > self._max_recursive_depth:
                if self._debug:
                    self._changes_tree.add_child_under_cursor(change,Tag.SKIPPED)
                return
            
            # Enter record context if not already in it
            if not self._is_recording:
                with self.record():
                    self.apply_change(change)
                return
            
            # Prevent infinite recursion
            # if change.topic_name in self._apply_change_call_stack:
            #     return
            
            # Apply the change

            old_value, new_value = topic.apply_change(change,notify_listeners=False)

            self._changes_list.append(change)

            if not topic.is_stateful() or self._inside_emit_change:
                # simply notify listeners without handling recursive calls or errors
                if self._debug:
                    with self._changes_tree.add_child_under_cursor(change,Tag.NOT_RECORDED):
                        topic.notify_listeners(change,old_value,new_value)
                else:
                    topic.notify_listeners(change,old_value,new_value)
                return
            
            

            node = self._transition_tree.add_child_under_cursor(change)
            with self._transition_tree.move_cursor(node):
                with self._changes_tree.add_child_under_cursor(change,Tag.NORMAL) if self._debug else nullcontext(): # debug
                    try:
                        with self._track_apply_change(change.topic_name):
                            with self.enter_emit_change() if isinstance(change,(EventChangeTypes.EmitChange,EventChangeTypes.ReversedEmitChange)) else nullcontext():
                                topic.notify_listeners(change,old_value,new_value)
                    except:
                        # Undo the subtree of changes which was caused in consequence of this change
                        if self._inside_emit_change:
                            raise RuntimeError("An error has occured inside an event change. Please avoid that. The state is now in an inconsistent state. The error was: \n" + str(traceback.format_exc()))
                        if topic.is_stateful():
                            logger.warning("An error has occured in the transition. Cleaning up the failed transition. The error was:\n" + str(traceback.format_exc()))
                            with self._block_recursion():
                                self._transition_tree.clear_subtree()
                        raise


    def undo(self, transition: Transition, action_source=0):
        # Record the changes made by the undo
        # Undo should not be recorded as a transition
        with self.record(action_source=action_source,emit_transition=False,phase=Phase.UNDOING):
            # Block recursive calls to change stateful topics. Only to undo the transition itself
            with self._block_recursion(1):
                # Revert the transition
                for change in reversed(transition.changes):
                    logger.debug("Undoing by change: " +str(change.inverse().serialize()))
                    self.apply_change(change.inverse())
    
    def redo(self, transition: Transition):
        # Record the changes made by the redo
        # Redo should not be recorded as a transition
        with self.record(emit_transition=False,phase=Phase.REDOING):
            # Block recursive calls to change stateful topics. Only to redo the transition itself
            with self._block_recursion(1):
                # Revert the transition
                for change in transition.changes:
                    logger.debug("Redoing change: " +str(change.serialize()))
                    self.apply_change(change)

    def do_after_transition(self,task): #TODO: thread safety?
        '''
        Run a task after the current transition is done. Changes made by the task will be separately recorded as the next transition.
        Do nothing if undoing or redoing.
        '''
        if self._phase == Phase.IDLE: 
            task()
        elif self._phase == Phase.FORWARDING:
            self._tasks_to_run_after_transition.append(task)
        else:
            return