import threading
from chatroom import ChatroomServer, ChatroomClient

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