#!/usr/bin/env python3

import argparse, io, json, select, socket as lib_socket, struct, sys, termios, time

from dts.protocol import Packet, PacketParser

parser = argparse.ArgumentParser(description="Arctic Wolf: contest management system")
parser.add_argument('--port', '-p', action='store', dest='port', required=True, help='Default port to listen')
parser.add_argument('-u', action='store', dest='unix', help='Unix socket for command console (not used by default).')
parser.add_argument('data', metavar='<data>', help='Prefix for data files.')
args = parser.parse_args()

def handle_socket( handle, events, callbacks ):
    queue = []
    for x in [select.EPOLLIN, select.EPOLLOUT, select.EPOLLERR]:
        if events & x == 0: continue
        events &= ~x
        if x in callbacks:
            queue.append((callbacks[x], []))
        else:
            print("ERROR: cannot handle event (handle = %d, event = %d)" % (handle, x))
    if events != 0:
        print("ERROR: cannot handle events (handle = %d, events = %d)" % (handle, events))
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
                print("ERROR: cannot handle %d" % handle, file=sys.stderr)
        return queue

def cb_unix( socket, peer ):
    print("new unix connection (handle = %d, remote = %s)" % (socket.fileno(), str(peer)))
    socket.close()
    return []
def cb_conn_create( socket ):
    def result( data ):
        socket.send((json.dumps(data) + '\n').encode("utf-8"))
        return []
    def handle_packet( data ):
        try:
            data = json.loads(data.decode("utf-8"))
        except ValueError as error:
            print("ERROR while decoding packet:", error)
            return result(False)
        print('packet received: %s' % data)
        # socket.send((json.dumps({'result': 'error', 'description': 'under contruction (feature not implemented)'}) + '\n').encode("utf-8"))
        return result(False)
    tail = b''
    def cb_conn( data ):
        nonlocal tail
        # print("data received: %d bytes: %s" % (len(data), ''.join(['.' if x < 32 or x >= 127 else chr(x) for x in data])))
        data = data.split(b'\n')
        tail += data[0]
        queue = []
        for x in data[1:]:
            queue.append((handle_packet, [tail]))
            tail = x
        return queue
    return cb_conn
def cb_main( socket, peer ):
    print("new main connection (handle = %d, remote = %s)" % (socket.fileno(), str(peer)))
    poll.add_peer(socket, cb_conn_create(socket))
    return []

poll = Poll()
if args.unix is not None:
    s = lib_socket.socket(lib_socket.AF_UNIX, lib_socket.SOCK_STREAM)
    s.bind(args.unix)
    s.listen(3)
    poll.add_listener(s, cb_unix)
s = lib_socket.socket(lib_socket.AF_INET, lib_socket.SOCK_STREAM)
s.setsockopt(lib_socket.SOL_SOCKET, lib_socket.SO_LINGER, struct.pack('II', 1, 0))
s.bind(('', int(args.port)))
s.listen(100)
poll.add_listener(s, cb_main)

log_index = open(args.data + '.bin', 'r+b')
size = log_index.seek(0, io.SEEK_END)
print(("opened index log (" + args.data + '.bin' + "), size: %d bytes") % size)

with open(args.data + '.log', 'r') as log_event:
    for line in log_event.readlines():
        print("replay log line: %s" % line)
    size = log_event.tell()
print("readed %d bytes from event log" % size)
log_event = open(args.data + '.log', 'a')
assert size == log_event.tell()

while True:
    queue = poll() # Вместе вырвем себе мозг?
    for action, arguments in queue:
        # print("queue call: action =", action, 'arguments =', arguments)
        # r = action(*arguments)
        # print("r =", r)
        # queue.extend(r)
        queue.extend(action(*arguments))

