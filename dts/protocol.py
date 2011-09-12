from . import config

class Packet:
    def __init__( self, data = {} ):
        self.__data = data
    def __call__( self ):
        return b'\0---\0' + b'\0'.join([self.__encode(key) + b'=' + self.__encode(self.__data[key]) for key in sorted(self.__data)]) + b'\0+++\0'
    def __encode( self, data ):
        return b''.join([bytes([x]) if x >= 0x20 else bytes([0x18, x ^ 0x40]) for x in data.encode(config.encoding)])

class PacketParser:
    def __init__( self ):
        self.__queue = []
        self.__state = self.__error() # easiest way to reset DFA

    def __dfa_magic_create( self, index ):
        magic = b'\0---\0'
        def __dfa_magic( key ):
            # print("[debug] dfa_magic(index = %d, key = %c %d)" % (index, key if key >= 0x20 else '.', key))
            if magic[index] != key:
                return self.__error()
            if index + 1 == len(magic):
                return self.__dfa_bv_create(False, False)
            return self.__dfa_magic_create(index + 1)
        return __dfa_magic

    def __dfa_bv_create( self, fv, fx ):
        def __dfa_bv( key ):
            # print("[debug] dfa_bv(fv = %s, fx = %s, key = %c %d)" % (str(fv), str(fx), key if key >= 0x20 else '.', key))
            if key == 0 and not fx:
                self.__data[self.__key.decode(config.encoding)] = self.__value.decode(config.encoding) if self.__value is not None else None
                self.__key = b''
                self.__value = None
                return self.__dfa_exit_create(1)
            if key == 0x18:
                if fx: return self.__error()
                return self.__dfa_bv_create(fv, True)
            if fx:
                key ^= 0x40
                if key >= 0x20: return self.__error()
            if key == ord('=') and not fv:
                self.__value = b''
                return self.__dfa_bv_create(True, False)
            if fv:
                self.__value += bytes([key])
            else:
                self.__key += bytes([key])
            return self.__dfa_bv_create(fv, False)
        return __dfa_bv

    def __dfa_exit_create( self, index ):
        exit = b'\0+++\0'
        def __dfa_exit( key ):
            # print("[debug] dfa_exit(index = %d, key = %c %d)" % (index, key if key >= 0x20 else '.', key))
            if exit[index] != key:
                if index == 1:
                    self.__key += bytes([key])
                    return self.__dfa_bv_create(False, False)
                return self.__error()
            if index + 1 == len(exit):
                return self.__append()
            return self.__dfa_exit_create(index + 1)
        return __dfa_exit

    def __error( self ):
        self.__key = b''
        self.__value = None
        self.__data = {}
        return self.__dfa_magic_create(0)
    def __append( self ):
        self.__queue.append(self.__data)
        return self.__error()

    def add( self, data ):
        for x in data:
            self.__state = self.__state(x)

    def __call__( self ):
        queue = self.__queue
        self.__queue = []
        return queue

