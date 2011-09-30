#!/usr/bin/env python3

import argparse, io, json, select, socket, struct, sys

from dts.protocol import Packet, PacketParser
from wolf import core, data, poll
from wolf.common import log

parser = argparse.ArgumentParser(description="Arctic Wolf: contest management system")
parser.add_argument('--port', '-p', action='store', dest='port', required=True, help='Default port to listen')
parser.add_argument('-u', action='store', dest='unix', help='Unix socket for command console (not used by default).')
parser.add_argument('data', metavar='<data>', help='Prefix for data files.')
args = parser.parse_args()

def cb_unix( socket, peer ):
    log("new unix connection (handle = %d, remote = %s)" % (socket.fileno(), str(peer)))
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
            log("ERROR while decoding packet: %s" % str(error))
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
    log("new main connection (handle = %d, remote = %s)" % (socket.fileno(), str(peer)))
    global actions
    poll.add_peer(socket, cb_conn_create(socket, actions))
    return []

poll = poll.Poll()
if args.unix is not None:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(args.unix)
    s.listen(3)
    poll.add_listener(s, cb_unix)
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('II', 1, 0))
s.bind(('127.0.0.1', int(args.port)))
s.listen(100)
poll.add_listener(s, cb_main)


def json_binary_decode( data ):
    data = data.encode("ascii").split(b'@')
    result = data[0]
    for x in data[1:]:
        result += bytes([int(x[0:2], 16)]) + x[2:]
    return result
def json_binary_encode( data ):
    result = ''
    for x in data:
        if 32 <= x <= 126 and x != ord('@'):
            result += chr(x)
        else:
            result += "@%02x" % x
    return result

def replay_wolf( timestamp, parameters ):
    global wolf, data
    wolf = core.Wolf(timestamp)
    data.replayers = wolf.replayers()

def action_create( parameters, continuation ):
    def action( data ):
        for x in parameters:
            if x not in data:
               return False
        return continuation(*[data[x] for x in parameters])
    return action

def action_compiler_add( id, binary, compile, run ):
    if wolf.compiler_get(id) is not None:
        return False
    data.create("compiler.add", [id, binary, compile, run])
    return True
def action_compiler_info( id ):
    if isinstance(id, list):
        return [action_compiler_info(x) for x in id]
    compiler = wolf.compiler_get(id)
    return {'id': compiler.id, 'binary': compiler.binary, 'compile': compiler.compile, 'run': compiler.run} if compiler is not None else False
def action_compiler_list():
    return wolf.compiler_list()
def action_compiler_remove( id ):
    if wolf.compiler_get(id) is None:
        return False
    data.create("compiler.remove", id)
    return True

def action_problem_checker_set( id, name, source, compiler ):
    if id < 0 or id >= wolf.problem_count():
        return False
    if wolf.compiler_get(compiler) is None:
        return False
    source = data.save(json_binary_decode(source))
    data.create("problem.checker.set", [id, name, source, compiler])
    return True
def action_problem_checker_source( id ):
    if id < 0 or id >= wolf.problem_count():
        return False
    checker = wolf.problem_get(id).checker
    if checker is None:
        return None
    return json_binary_encode(data.load(checker.source))
def action_problem_create( name, full ):
    id = wolf.problem_count()
    data.create("problem.create", [id, name, full])
    return id

def action_team_add( login, name, password ):
    if wolf.team_get(login) is not None:
        return False
    data.create("team.add", [login, name, password])
    return True
def action_team_login( login, password ):
    team = wolf.team_get(login)
    return team is not None and team.login == login and team.password == password
def action_team_info( login ):
    if isinstance(login, list):
        return [action_team_info(x) for x in login]
    team = wolf.team_get(login)
    return {'login': team.login, 'name': team.name} if team is not None else False

actions = {
    'ping': lambda data: True,
    'compiler.add': action_create(['id', 'binary', 'compile', 'run'], action_compiler_add),
    'compiler.info': action_create(['id'], action_compiler_info),
    'compiler.list': action_create([], action_compiler_list),
    'compiler.remove': action_create(['id'], action_compiler_remove),
    # 'problem.checker.default'
    'problem.checker.set': action_create(["id", "name", "source", "compiler"], action_problem_checker_set),
    'problem.checker.source': action_create(["id"], action_problem_checker_source),
    'problem.create': action_create(['name', 'full'], action_problem_create),
    'team.add': action_create(['login', 'name', 'password'], action_team_add),
    'team.info': action_create(['login'], action_team_info),
    'team.login': action_create(['login', 'password'], action_team_login)
}
replayers = {
    'wolf': replay_wolf
}
wolf = None

data = data.Data(replayers, args.data + '.bin', args.data + ".log")
data.start()

sys.stdout.flush()
while True:
    queue = poll() # Вместе вырвем себе мозг?
    for action, arguments in queue:
        queue.extend(action(*arguments))

