import hashlib, io, sys, time
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
        log("read %d bytes from event log (%s)" % (size, self.__logfile))

        self.__log = open(self.__logfile, 'a')
        assert size == self.__log.tell()

    def __replay( self, line ):
        data = line.split()
        timestamp, event = data[0:2]
        if event not in self.replayers:
            log("FATAL: cannot replay event \"%s\" (no such event)" % event)
            sys.exit(1)
        log("replay log event: %s" % str(data))
        data = data[2:]
        if not isinstance(data, list):
           data = [data]
        self.replayers[event](int(timestamp), [None if x == '-' else ''.join(self.__decode(x[1:-1])) for x in data])

    def create( self, event, parameters ):
        line = [str(int(time.time())), event] + ['-' if x is None else '"' + ''.join(self.__encode(str(x))) + '"' for x in parameters]
        line = '\t'.join(line)
        print(line, file=self.__log)
        self.__log.flush()
        self.__replay(line)

    def save( self, content, name=None ):
        assert isinstance(content, bytes)
        hash = hashlib.md5(content).hexdigest()
        if name is None: name = hash
        start = self.__bin.tell()
        size = len(content)
        self.__bin.write(content)
        self.__bin.flush()
        self.create('content', [hash, name, start, size])
        return hash

    def load( self, start, size ):
        assert isinstance(start, int) and isinstance(size, int)
        assert size >= 0 and start >= 0 and start + size <= self.__bin.tell()
        self.__bin.seek(start)
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


