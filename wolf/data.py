import io, sys, time
from .common import log

class Data:
    def __init__( self, replayers, binfile, logfile ):
        self.replayers = replayers
        self.__binfile, self.__logfile = binfile, logfile

    def start( self ):
        self.__bin = open(self.__binfile, 'r+b')
        size = self.__bin.seek(0, io.SEEK_END)
        log(("opened index log (%s), size: %d bytes") % (self.__binfile, size))

        with open(self.__logfile, 'r') as events:
            for line in events.readlines():
                self.__replay(line)
            size = events.tell()
        log("read %d bytes from event log" % size)

        self.__log = open(self.__logfile, 'a')
        assert size == self.__log.tell()

    def __replay( self, line ):
        data = line.split()
        timestamp, event = data[0:2]
        if event not in self.replayers:
            log("FATAL: cannot replay event \"%s\" (no such event)" % event)
            sys.exit(1)
        log("replay log event: %s" % str(data))
        self.replayers[event](timestamp, [None if x == '-' else ''.join(self.__decode(x[1:-1])) for x in data[2:]])

    def create( self, event, parameters ):
        line = [str(int(time.time())), event] + ['-' if x is None else '"' + ''.join(self.__encode(str(x))) + '"' for x in parameters]
        line = '\t'.join(line)
        print(line, file=self.__log)
        self.__log.flush()
        self.__replay(line)

    def save( self, content ):
        assert isinstance(content, bytes)
        r = "%d+%d" % (self.__bin.tell(), len(content))
        self.__bin.write(content)
        self.__bin.flush()
        return r

    def load( self, pointer ):
        offset, size = [int(x) for x in pointer.split('+')]
        assert size >= 0 and offset >= 0 and offset + size <= self.__bin.tell()
        self.__bin.seek(offset)
        r = self.__bin.read(size)
        self.__bin.seek(0, io.SEEK_END)
        return r

    @staticmethod
    def __decode( s ):
        f = False
        for ch in s:
            if f:
                yield chr(ord(ch) - 48)
                f = False
            elif ch == '\\':
                f = True
            else:
                yield ch

    @staticmethod
    def __encode( s ):
        for ch in s:
            if ord(ch) > 32 and ch != '\\' and ch != '"':
                yield ch
            else:
                yield '\\'
                yield chr(ord(ch) + 48)


