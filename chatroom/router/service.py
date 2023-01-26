from typing import Dict

from chatroom.router.endpoint import Endpoint

class Service:
    def __init__(self,name:str,provider:Endpoint) -> None:
        self.name = name
        self.provider = provider

class Request:
    def __init__(self,id:int,source_client) -> None:
        self.id = id
        self.source_client = source_client