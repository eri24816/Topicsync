import threading
from termcolor import colored
lock = threading.Lock()
DEBUG = 1
INFO = 2
WARNING = 3
ERROR = 4

level_names = {
    DEBUG: 'DEBUG',
    INFO: 'INFO',
    WARNING: 'WARNING',
    ERROR: 'ERROR'
}

default_color = {
    DEBUG: 'blue',
    INFO: 'white',
    WARNING: 'yellow',
    ERROR: 'red'
}

class Logger:
    def __init__(self,level=INFO,prefix=""):
        self._level = level
        self._prefix = prefix

    def log(self,message,level=INFO,color=None,on_color=None):
        if level >= self._level:
            message = f'{self._prefix} [{level_names[level]}] {message}'
            if color is None:
                color = default_color[level]
            message = colored(message,color,on_color)
            lock.acquire()
            print(message,flush=True)
            lock.release()

    def debug(self,message):
        self.log(message,DEBUG)

    def info(self,message):
        self.log(message,INFO)

    def warning(self,message):
        self.log(message,WARNING)

    def error(self,message):
        self.log(message,ERROR)