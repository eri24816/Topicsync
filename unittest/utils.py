import threading
import random


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