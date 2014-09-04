import sys, time

class Log:
    def __init__( self ):
        pass
    def __call__( self, message, level='' ):
        print("[%s%s]" % (time.strftime("%Y-%m-%d %H:%M:%S"), level), message)
        sys.stdout.flush()
    def info( self, message ):
        self.__call__(message, level=" info")
    def debug( self, message ):
        self.__call__(message, level=" debug")
    def write( self, message, end='\n' ):
        print(message, end=end)
        sys.stdout.flush()

log = Log()

