import os.path
from .common import log
from dts.protocol import Packet

class Judge:
    OK, CE, FAIL = range(3)
    status_str = ["OK", "CE", "Fail"]

    def __init__( self, socket, callback_ready ):
        self.__socket, self.__ready = socket, callback_ready
        self.__message_id = 0
        self.__response = {None: self.__authorize}
        self.__status = {Judge.status_str[x]: x for x in [Judge.OK, Judge.CE, Judge.FAIL]}
    def name( self ):
        return self.__name

    def __authorize( self, packet ):
        del self.__response[None]
        if b'Password' not in packet or b'Name' not in packet:
            log("disconnecting judge (bad authorization)")
            # todo: disconnect
            return []
        # todo: check password
        self.__name = packet[b'Name'].decode('utf8')
        log("new judge registered in system: %s" % self.__name)
        return self.__ready(self)

    def __normal( self, callback, parameters ):
        def response( packet ):
            del self.__response[packet[b'ID']]
            status = packet.get(b'Status').decode('iso8859-1')
            if status == 'FREQ':
                files = set([x.split('\\')[0] for x in packet[b'FREQ'].decode('utf-8').split('\r\n') if x != ''])
                self.__query(files)
                return []
            if status not in self.__status:
                log("ERROR: unknown judge status: %s" % status)
                log("full packet: %s" % str(packet))
                # todo: disconnect
                return []
            return [
                (self.__ready, (self,)),
                (callback, [self.__status[status]] + [
                   (f if f is not None else lambda x: x)(packet.get(k, d)) for k, d, f in parameters
                ])
            ]
        return response

    def __compiled( self, callback ):
        return self.__normal(callback, [
            (b'ExeFile', None, None),
            (b'UtilityOutput', b'', None)
        ])
    def __tested( self, callback ):
        return self.__normal(callback, [
            (b'MaxTime', None, lambda x: 1e-7 * int(x)), # testsys judge returns time in 1/10⁷ seconds
            (b'MaxMemory', None, None)
        ])

    def receive( self, packet ):
        id = packet.get(b'ID')
        if id not in self.__response:
            log("ERROR: unexpected packet from judge: %s" % str(packet))
            return []
        return self.__response[id](packet)

    def compile( self, command, source, callback ):
        id = ('id_%08d' % self.__message_id).encode('ascii')
        self.__message_id += 1
        self.__response[id] = self.__compiled(callback)
        source_data = ('%s\\%s>%d|\r' % (source.hash, source.name, source.time)).encode('utf-8') + source.load()
        self.__socket.send(Packet({
            b'ID': id,
            b'Command': b'compile',
            b'Compiler': command.encode('utf-8'),
            b'Source': os.path.splitext(source.name)[0].encode('utf-8'), # specifix of testsys judge, remove as soon as possible
            b'SourceFile': source_data,
            # b'BinaryName': binary_name.encode('utf-8') # not supported by judge
        })())

    def test( self, *, binary, test, answer, input='stdin', output='stdout', time_limit, memory_limit, checker, callback ):
        def query( files ):
            id = ('id_%08d' % self.__message_id).encode('ascii')
            self.__message_id += 1
            path = lambda f: \
                    ('%s\\%s>%d|\r' % (f.hash, f.name, f.time)).encode('utf-8') + f.load() \
                if f.hash in files else \
                    ('%s\\%s>%d' % (f.hash, f.name, f.time)).encode('utf-8')
            self.__response[id] = self.__tested(callback)
            self.__socket.send(Packet({
                b'ID': id,
                b'Command': b'test',
                b'Source': os.path.splitext(binary.name)[0].encode('utf-8'), # that's so-called 'main class name', ask KOTEHOK (vk.com/kotehok) for its meaning
                b'ExeFile': path(binary),
                b'TestPath': path(test),
                b'AnswerPath': path(answer),
                b'InputName': input,
                b'OutputName': output,
                b'TimeLimit': ('%d' % int(1000 * time_limit)).encode('utf-8'),
                b'MemoryLimit': ('%d' % memory_limit).encode('utf-8'),
                b'CheckerPath': path(checker)
            })())
        self.__query = query
        query(set())

