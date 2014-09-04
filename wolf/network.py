import select, socket
from .common import log

class Socket:
    def __init__( self, handle ):
        self.__handle = handle
        self.send = handle.send

def handle_socket( handle, events, callbacks ):
    for x in [select.EPOLLIN, select.EPOLLOUT, select.EPOLLERR, select.EPOLLHUP]:
        if events & x == 0: continue
        events &= ~x
        if x in callbacks:
            yield (callbacks[x], ())
        else:
            log("ERROR: cannot handle event (handle = %d, event = %d)" % (handle, x))
    if events != 0:
        log("ERROR: cannot handle events (handle = %d, events = %d)" % (handle, events))

class Poll:
    def __init__( self ):
        self.__poll = select.epoll()
        self.__actions = {}

    def __add( self, socket, action, halt=None ):
        socket_handle = socket.fileno()
        def handle( handle, events ):
            assert handle == socket_handle
            return handle_socket(handle, events, {
                select.EPOLLIN: action,
                select.EPOLLHUP: halt
                # todo: use cb_halt for handing EPOLLHUP and EPOLLERR
            })
        self.__actions[socket_handle] = handle
        self.__poll.register(socket, select.EPOLLIN)
        return socket_handle

    def __disconnect( self, socket ):
        self.__poll.unregister(socket)
        del self.__actions[socket.fileno()]
        socket.close()

    @staticmethod
    def __receive( handle, cb_data, cb_halt ):
        try:
            data = handle.recv(4096, socket.MSG_DONTWAIT)
            return [(cb_data, (data,))]
        except IOError as e:
            log("EXCEPTION: %s" % str(e))
            return [(cb_halt, ())]

    def add_listener( self, socket, callback ):
        def action():
            nonlocal socket, callback
            handle, peer = socket.accept()
            wrapper = Socket(handle)
            def init( cb_data, cb_halt ):
                wrapper.disconnect = lambda: self.__disconnect(handle)
                self.__add(handle, lambda: self.__receive(handle, cb_data, cb_halt), cb_halt)
                return []
            return [(callback, (peer, wrapper, init))]
        return self.__add(socket, action)

    def __call__( self ):
        queue = []
        for handle, events in self.__poll.poll():
            if handle in self.__actions:
                queue.append((self.__actions[handle], (handle, events)))
            else:
                log("ERROR: cannot handle %d" % handle)
        return queue

