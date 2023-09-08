
import http
import json
from time import sleep
import traceback
from websockets.server import WebSocketServerProtocol, serve
import asyncio
from os.path import join

from chatroom.state_machine.changes_tree import ChangesTree

here = __file__.replace("debugger.py", "")

class Debugger:
    def __init__(self, port=8800, host='localhost') -> None:
        self._port = port
        self._host = host
        self._clients:list[WebSocketServerProtocol] = []
        self._change_trees:list[dict] = []

    async def run(self):
        await serve(self._handler, self._host, self._port ,process_request=self._process_request)
        
    async def _process_request(self, path, request_headers):

        if path == "/ws":
            return None

        #print(path)
        
        content_type = "text/plain"
        status = http.HTTPStatus.OK
        if path == "/":
            content = open(join(here,"index.html"), "rb").read()
            content_type = "text/html"
        elif path.endswith(".js"):
            content = open(join(here,path[1:]), "rb").read()
            content_type = "application/javascript"
        elif path.endswith(".css"):
            content = open(join(here,path[1:]), "rb").read()
            content_type = "text/css"
        else:
            try:
                content = open(join(here,path[1:]), "rb").read()
            except:
                content = b""
                status = http.HTTPStatus.NOT_FOUND
        return (
            status,
            [
                ("Content-Type", content_type),
                ("Content-Length", str(len(content))),
            ],
            content,
        )

    async def _handler(self, ws: WebSocketServerProtocol, path):
        self._clients.append(ws)
        
        try:
            #await ws.send(json.dumps({"name": "1", "children": [{"name": "2"}, {"name": "3"}]}))
            for existing_trees in self._change_trees:
                await ws.send(json.dumps(existing_trees))
            while True:
                data = await ws.recv()

        except Exception as e:
            self._clients.remove(ws)
            #print("disconnected",traceback.format_exc())

    def send(self, data):
        for client in self._clients:
            asyncio.get_event_loop().create_task(client.send(json.dumps(data)))

    def push_changes_tree(self, change_tree:ChangesTree):
        change_tree_dict = change_tree.serialize()
        self._change_trees.append(change_tree_dict)
        self.send(change_tree_dict)

if __name__ == "__main__":
    debugger = Debugger()
    asyncio.get_event_loop().run_until_complete(debugger.run())
    asyncio.get_event_loop().run_forever()
    sleep(10000000)