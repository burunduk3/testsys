from .common import log
from dts.protocol import Packet

class Judge:
    CONNECTING, READY, COMPILE = range(3)
    def __init__( self, socket, ready_callback ):
        self.__socket, self.__ready = socket, ready_callback
        self.__state = Judge.CONNECTING
        self.__message_id = 0
    def state( self ):
        return self.__state
    def name( self ):
        return self.__name
    def receive( self, packet ):
        if self.__state is Judge.CONNECTING:
            if b'Password' not in packet or b'Name' not in packet:
                log("ERROR: unexpected packet from judge: %s" % str(packet))
                return []
            # todo: check password
            self.__state = Judge.READY
            self.__name = packet[b'Name'].decode('utf8')
            log("new judge registered in system: %s" % self.__name)
            return self.__ready(self)
        elif self.__state is Judge.COMPILE:
            if b'Status' not in packet:
                log("ERROR: unexpected packet from judge: %s" % str(packet))
            if packet[b'Status'] == b'OK':
                self.__state = Judge.READY
                return [(self.__ready, [self]), (self.__callback_ok, (packet[b'ExeFile'], packet[b'UtilityOutput']))]
            else:
                log("ERROR: unexpected packet from judge: %s" % str(packet))
        else:
            log("ERROR: unexpected packet from judge: %s" % str(packet))
        return []

    def compile( self, command, name, source_name, source_data, callback_ok, callback_error ):
        self.__callback_ok, self.__callback_error = callback_ok, callback_error
        self.__state = Judge.COMPILE
        self.__socket.send(Packet({
            b'ID': ('id_%08d' % self.__message_id).encode('ascii'),
            b'Command': b'compile',
            b'Compiler': command.encode('utf-8'),
            b'Source': name.encode('utf-8'),
            b'SourceFile': source_name.encode('utf-8') + b'|\r' + source_data
        })())
        self.__message_id += 1

