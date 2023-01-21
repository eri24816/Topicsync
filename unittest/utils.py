import threading
from chatroom import ChatroomServer, ChatroomClient
import random

def create_server():
    server = ChatroomServer()
    server_thread = threading.Thread(target=server.Start)
    server_thread.daemon = True
    server_thread.start()
    return server

def get_free_port():
    from socket import socket
    with socket() as s:
        s.bind(('',0))
        return int(s.getsockname()[1])
    
class Empty:
    def __init__(self,**kwargs) -> None:
        for key,value in kwargs.items():
            setattr(self,key,value)

def random_combinations(n,**kwargs):
    for i in range(n):
        yield {key: random.choice(value) for key,value in kwargs.items()}