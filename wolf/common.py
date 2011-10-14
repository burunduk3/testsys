import sys, time

class Log:
    def __init__( self ):
        pass
    def __call__( self, message ):
        print(time.strftime("[%Y-%m-%d %H:%M:%S]"), message)
        sys.stdout.flush()
    def write( self, message, end='\n' ):
        print(message, end=end)
        sys.stdout.flush()

log = Log()

