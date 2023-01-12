class Request:
    def __init__(self,id,on_response) -> None:
        self.id = id
        self.on_response = on_response
        