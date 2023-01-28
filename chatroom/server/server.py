from typing import Dict, List, TypeVar, Type

from chatroom.router.router import ChatroomRouter
from chatroom.router.endpoint import PythonEndpoint
from chatroom.topic import StringTopic, Topic, UListTopic, TopicFactory
from chatroom.logger import Logger, DEBUG
from ..command import ChangeCommand, CommandManager
from chatroom.topic_change import Change, InvalidChangeException, UListChangeTypes

class ChatroomServer:
    def __init__(self,port) -> None:
        self._logger = Logger(DEBUG,"Server")
        self._command_manager = CommandManager(on_recording_stop=self._OnRecordingStop)
        self._endpoint = PythonEndpoint(self)
        self._router = ChatroomRouter(self._endpoint,port=port)
        self._topics : Dict[str,Topic] = {}
        self._AddTopicAndTrackChildren('','string')
    
    '''
    Callbacks
    '''

    def _OnRecordingStop(self,recorded_commands):
        '''
        Called when the command manager finishes recording
        '''
        command_dicts = [command.Serialize() for command in recorded_commands]
        self._endpoint.SendToRouter("update",changes = command_dicts)
        self._command_manager.Commit()

    def _OnRegisterChild(self,parent_topic,base_name,type):
        '''
        Called when a child topic is registered
        '''
        try:
            children_list = self._topics[f'/_cr/children/{parent_topic._name}']
        except KeyError:
            raise ValueError(f'You can\'t create a child of topic {parent_topic._name}')
        assert isinstance(children_list,UListTopic)

        if {'name':base_name,'type':type} in children_list.GetValue():
            return self._topics[f'{parent_topic._name}/{base_name}']
        else:
            children_list.Append({'name':base_name,'type':type})
            return self._topics[f'{parent_topic._name}/{base_name}']

    '''
    Interface for router
    '''

    def _handle_client_update(self,client,changes):
        try:
            for item in changes:
                topic_name, change_dict = item['topic_name'], item['change']
                topic = self._topics[topic_name]
                change = topic.DeserializeChange(change_dict)
                topic.ApplyChangeExternal(change)
                
        except InvalidChangeException as e:
            self._command_manager.Reset()
            self._endpoint.SendToRouter("reject_update",client=client,topic_name=changes[0]['topic_name'],change=changes[0]['change'],reason=str(e))
            return

    '''
    Shortcuts
    '''

    def GetTopic(self,topic_name):
        return self._topics[topic_name]
    
    def _AddTopic(self,name,type,verify_change=None):
        topic = self._topics[name] = TopicFactory(name,type,self._OnRegisterChild,lambda name: self._topics[name],self._command_manager)
        self._logger.Debug(f"Added topic {name} of type {type}")
        return topic
    
    def _AddTopicAndTrackChildren(self,name,type):
        self._AddTopic(name,type)
        children_list = self._AddTopic(f'/_cr/children/{name}','u_list',verify_children_list_change)
        def verify_children_list_change(old:List,new:List,change:Change):
            if isinstance(change,UListChangeTypes.AppendChange):
                if change.item in old:
                    raise InvalidChangeException(f"Child {change.item} already exists")
            elif isinstance(change,UListChangeTypes.SetChange):
                # no duplicates
                if len(set(new)) != len(new):
                    raise InvalidChangeException("Duplicate children")

        assert isinstance(children_list,UListTopic)
        children_list.on_append += lambda data: self._OnChildrenListAppend(name,data)
        children_list.on_remove += lambda data: self._OnChildrenListRemove(name,data)
        return self._topics[name]

    def _OnChildrenListAppend(self,parent_name,data):
        name = f'{parent_name}/{data["name"]}'
        type = data['type']
        self._AddTopicAndTrackChildren(name,type)

    def _RemoveTopic(self,name):
        del self._topics[name]
        self._logger.Debug(f"Removed topic {name}")

    def _RemoveTopicAndUntrackChildren(self,name):
        self._RemoveTopic(name)
        self._RemoveTopic(f'/_cr/children/{name}')

    def _OnChildrenListRemove(self,parent_name,data):
        name = data['name']
        self._RemoveTopicAndUntrackChildren(f'{parent_name}/{name}')