import threading
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

class Logger:
    def __init__(self,level=INFO,prefix=""):
        self._level = level
        self._prefix = prefix

    def log(self,message,level=INFO):
        lock.acquire()
        if level >= self._level:
            print(f'{self._prefix} [{level_names[level]}] {message}',flush=True)
        lock.release()

    def debug(self,message):
        self.log(message,DEBUG)

    def info(self,message):
        self.log(message,INFO)

    def warning(self,message):
        self.log(message,WARNING)

    def error(self,message):
        self.log(message,ERROR)