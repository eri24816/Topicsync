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

    def Log(self,message,level=INFO):
        if level >= self._level:
            print(f'{self._prefix} [{level_names[level]}] {message}')

    def Debug(self,message):
        self.Log(message,DEBUG)

    def Info(self,message):
        self.Log(message,INFO)

    def Warning(self,message):
        self.Log(message,WARNING)

    def Error(self,message):
        self.Log(message,ERROR)