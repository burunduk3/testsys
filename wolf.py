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
def cb_conn_create( socket, actions ):
    def result( data ):
        socket.send((json.dumps(data) + '\n').encode("utf-8"))
        return []
    def handle_packet( data ):
        try:
            data = json.loads(data.decode("utf-8"))
        except ValueError as error:
            print("ERROR while decoding packet:", error)
            return result(False)
        if not isinstance(data, dict) or 'action' not in data:
            return result(False)
        return result(False if data['action'] not in actions else actions[data['action']](data));
    tail = b''
    def cb_conn( data ):
        if len(data) == 0:
            poll.remove(socket.fileno())
            socket.close()
            return []
        nonlocal tail
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
    global actions
    poll.add_peer(socket, cb_conn_create(socket, actions))
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

class Team:
    def __init__( self, login, name, password ):
        self.login, self.name, self.password = login, name, password

class Wolf:
    def __init__( self, timestamp ):
        self.__timestamp = timestamp
        self.__teams = {}
    def replayers( self ):
        return {
            'team.add': self.replay_team_add
        }
    def replay_team_add( self, timestamp, parameters ):
        login, name, password = parameters
        self.__teams[login] = Team(login, name, password)
    def team_get( self, login ):
        return self.__teams[login] if login in self.__teams else None

def replay_wolf( timestamp, parameters ):
    global wolf, replayers
    wolf = Wolf(timestamp)
    replayers = wolf.replayers()
def levpar_decode( s ):
    f = False
    for ch in s:
        if f:
            yield chr(ord(ch) - 48)
            f = False
        elif ch == '\\':
            f = True
        else:
            yield ch
def levpar_encode( s ):
    for ch in s:
        if ord(ch) > 32 and ch != '\\':
            yield ch
        else:
            yield '\\'
            yield chr(ord(ch) + 48)
def replay_logevent( line ):
    global replayers
    data = line.split()
    timestamp, event = data[0:2]
    if event not in replayers:
        print("FATAL: cannot replay event %s (no such event)" % event)
        sys.exit(1)
    print("replay log event: %s" % str(data))
    replayers[event](timestamp, [''.join(levpar_decode(x)) for x in data[2:]])
def create_logevent( event, parameters ):
    line = [str(int(time.time())), event] + [''.join(levpar_encode(x)) for x in parameters]
    line = '\t'.join(line)
    print(line, file=log_event)
    log_event.flush()
    replay_logevent(line)

def action_create( parameters, continuation ):
    def action( data ):
        for x in parameters:
            if x not in data:
               return False
        return continuation(*[data[x] for x in parameters])
    return action
def action_team_add( login, name, password ):
    if wolf.team_get(login) is not None:
        return False
    create_logevent("team.add", [login, name, password])
    return True
def action_team_login( login, password ):
    team = wolf.team_get(login)
    return team is not None and team.login == login and team.password == password

actions = {
    'ping': lambda data: True,
    'team.add': action_create(['login', 'name', 'password'], action_team_add),
    'team.login': action_create(['login', 'password'], action_team_login)
}
replayers = {
    'wolf': replay_wolf
}
wolf = None

log_index = open(args.data + '.bin', 'r+b')
size = log_index.seek(0, io.SEEK_END)
print(("opened index log (" + args.data + '.bin' + "), size: %d bytes") % size)

with open(args.data + '.log', 'r') as log_event:
    for line in log_event.readlines():
        replay_logevent(line)
    size = log_event.tell()
print("readed %d bytes from event log" % size)
log_event = open(args.data + '.log', 'a')
assert size == log_event.tell()

while True:
    queue = poll() # Вместе вырвем себе мозг?
    for action, arguments in queue:
        queue.extend(action(*arguments))

