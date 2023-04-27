from typing import Callable


class Service:
    def __init__(self,callback:Callable,pass_client_id) -> None:
        self.callback = callback
        self.pass_client_id = pass_client_id
        