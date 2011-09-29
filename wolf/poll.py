import select, socket as lib_socket
from .common import log

def handle_socket( handle, events, callbacks ):
    queue = []
    for x in [select.EPOLLIN, select.EPOLLOUT, select.EPOLLERR]:
        if events & x == 0: continue
        events &= ~x
        if x in callbacks:
            queue.append((callbacks[x], []))
        else:
            log("ERROR: cannot handle event (handle = %d, event = %d)" % (handle, x))
    if events != 0:
        log("ERROR: cannot handle events (handle = %d, events = %d)" % (handle, events))
    return queue

class Poll:
    def __init__( self ):
        self.__poll = select.epoll()
        self.__actions = {}
    def __add( self, socket, action ):
        socket_handle = socket.fileno()
        def handle( handle, events ):
            assert handle == socket_handle
            return handle_socket(handle, events, {
                select.EPOLLIN: action
            })
        self.__actions[socket_handle] = handle
        self.__poll.register(socket, select.EPOLLIN)
        return socket_handle
    def add_listener( self, socket, callback ):
        return self.__add(socket, lambda: [(callback, socket.accept())])
    def add_peer( self, socket, callback ):
        return self.__add(socket, lambda: [(callback, [socket.recv(4096, lib_socket.MSG_DONTWAIT)])])
    def remove( self, handle ):
        self.__poll.unregister(handle)
        del self.__actions[handle]
    def __call__( self ):
        queue = []
        for handle, events in self.__poll.poll():
            if handle in self.__actions:
                queue.append((self.__actions[handle], (handle, events)))
            else:
                log("ERROR: cannot handle %d" % handle)
        return queue

