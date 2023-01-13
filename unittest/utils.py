import threading
from chatroom import ChatroomServer, ChatroomClient

def create_server():
    server = ChatroomServer()
    server_thread = threading.Thread(target=server.Start)
    server_thread.daemon = True
    server_thread.start()
    return server