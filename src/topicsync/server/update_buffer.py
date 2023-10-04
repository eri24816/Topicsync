
from typing import Callable, DefaultDict, Dict, List
from topicsync.change import Change
from topicsync.state_machine.state_machine import StateMachine
from topicsync.topic import DictTopic
from topicsync.utils import Clock, astype
import logging
logger = logging.getLogger(__name__)

class UpdateBuffer:
    def __init__(self, state_machine: StateMachine, send_update: Callable[[List[Change],str],None]) -> None:
        self._state_machine = state_machine
        self._send_update = send_update
        self._to_send_later: DefaultDict[str, List[Change]] = DefaultDict(list)
        self._clock = Clock(0.2)
        self._clock.on_tick += self.flush

        # prevent problems when topic added or removed
        self.topic_dict = astype(self._state_machine.get_topic('_topicsync/topic_list'),DictTopic)
        self.topic_dict.on_remove += self.on_topic_remove

    async def run(self):
        await self._clock.run()

    def add_changes(self, changes: List[Change], action_id:str) -> None:
        to_send_now = []
        for change in changes:
            if not self._state_machine.has_topic(change.topic_name):
                continue
            if self._state_machine.get_topic(change.topic_name).is_stateful():
                to_send_now.append(change)
            else:
                self._to_send_later[change.topic_name].append(change)
        self._send_update(to_send_now,action_id)

    def on_topic_remove(self, topic_name: str) -> None:
        self._to_send_later.pop(topic_name,None)

    def flush(self):
        #merge changes with same topic name
        merged_changes: List[Change] = []

        for topic_name, changes in self._to_send_later.items():
            merged_changes += self._state_machine.get_topic(topic_name).merge_changes(changes)

        #send changes
        self._send_update(merged_changes,'clock')
        self._to_send_later = DefaultDict(list)
