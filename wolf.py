#!/usr/bin/env python3

import argparse, base64, io, json, select, socket, struct, sys

from dts.protocol import Packet, PacketParser
from wolf import core, data, network
from wolf.common import log
from wolf.queue import Queue
from wolf.judge import Judge
from wolf.magic import magic_parse

log.write(" === ARCTIC WOLF ===")

parser = argparse.ArgumentParser(description="Arctic Wolf: contest management system.")
parser.add_argument('--port', '-p', action='store', dest='port', required=True, help='Default port to listen.')
parser.add_argument('--judge-port', action='store', dest='judge_port', default=17239, help='Port to listen connections from judges.')
parser.add_argument('-u', action='store', dest='unix', help='Unix socket for command console (not used by default).')
parser.add_argument('data', metavar='<data>', help='Prefix for data files.')
args = parser.parse_args()

def cb_unix( socket, peer ):
    log("new unix connection (handle = %d, remote = %s)" % (socket.fileno(), str(peer)))
    socket.close()
    return []

def cb_main( peer, socket, init ):
    global net_actions
    log("INFO: peer %s connected" % str(peer))
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
        return result(net_actions.get(data['action'], lambda data: False)(data))
        # False if data['action'] not in actions else actions[data['action']](data));
    tail = b''
    def cb_data( data ):
        if len(data) == 0:
            log("INFO: abnormal disconnecting peer %s" % str(peer))
            socket.disconnect()
            return
        nonlocal tail
        data = data.split(b'\n')
        tail += data[0]
        for x in data[1:]:
            yield (handle_packet, (tail,))
            tail = x
    def cb_halt():
        log("INFO: peer %s disconnected" % str(peer))
        socket.disconnect()
        return []
    return init(cb_data, cb_halt)

def cb_judge( peer, socket, init ):
    parser = PacketParser(binary=True)
    judge = Judge(socket, judge_ready)
    def cb_data( data ):
        parser.add(data)
        return [(judge.receive, [x]) for x in parser()]
    def cb_halt():
        log("INFO: judge peer %s disconnected" % str(peer))
        # todo: shutdown judge and restart its active actions
        socket.disconnect()
        return []
    return init(cb_data, cb_halt)

poll = network.Poll()
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

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('II', 1, 0))
s.bind(('', int(args.judge_port)))
s.listen(100)
poll.add_listener(s, cb_judge)


def action_create( parameters, continuation, default = False ):
    def action( data ):
        if not default:
            for x in parameters:
                if x not in data:
                   return False
        return continuation(*[data.get(x, None) for x in parameters])
    return action

def action_archive_add( problem ):
    if not isinstance(problem, int) or \
       not 0 <= problem < wolf.problem_count() or \
       problem in wolf.archive_get().problems:
           # todo: optimize long check
           return False
    number = len(wolf.archive_get().problem_list)
    data.create('archive.add', [problem])
    return number
def action_archive_compiler_add( id, name ):
    if id in wolf.archive_get().compilers or wolf.compiler_get(id) is None:
        return False
    data.create('archive.compiler.add', [id, name])
    return True
def action_archive_compiler_list():
    compilers = wolf.archive_get().compilers
    return [{'id': x, 'name': compilers[x]} for x in sorted(compilers.keys())]
def action_archive_compiler_remove( id ):
    if id not in wolf.archive_get().compilers:
        return False
    data.create('archive.compiler.remove', [id])
    return True
def action_archive_count():
    return len(wolf.archive_get().problem_list)
def action_archive_list( start, limit ):
    return wolf.archive_get().problem_list[start:start + limit]
def action_archive_remove( id ):
    if not isinstance(id, int) or not 0 <= id < len(wolf.archive_get().problem_list):
        return False
    data.create("archive.remove", [id])
    return True
def action_archive_submit( team, problem, name, source, compiler ):
    archive = wolf.archive_get()
    if wolf.problem_get(problem) is None or wolf.compiler_get(compiler) is None or wolf.team_get(team) is None or \
            problem not in archive.problems or compiler not in archive.compilers:
        return False
    source = data.save(base64.b64decode(source.encode('ascii')), name)
    id = wolf.submit_count()
    data.create('archive.submit', [id, team, problem, source, compiler])
    return id
def action_archive_submits( team, problem, start, limit ):
    if not isinstance(start, int) or not isinstance(limit, int):
        return False
    archive = wolf.archive_get()
    if team is None and problem is None:
        submits = archive.submits_all
    elif team is None and problem is not None:
        submits = archive.submits_problem.get(problem, [])
    elif team is not None and problem is None:
        submits = archive.submits_team.get(team, [])
    else:
        submits = archive.submits.get((team, problem), [])
    if start < 0:
        limit += start
        start = 0
    if start >= len(submits):
        start = 0
        limit = 0
    if start + limit > len(submits):
        limit = len(submits) - start
    start = len(submits) - start - limit
    return {'count': len(submits), 'list': list(reversed(submits[start:start + limit]))}

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
def action_compiler_modify( id, binary, compile, run ):
    if not (isinstance(id, str) and (isinstance(binary, str) or binary is None) and (isinstance(compile, str) or compile is None) and (isinstance(run, str) or run is None)):
        return False
    if wolf.compiler_get(id) is None:
        return False
    data.create("compiler.modify", [id, binary, compile, run])
    return True
def action_compiler_remove( id ):
    if wolf.compiler_get(id) is None:
        return False
    data.create("compiler.remove", [id])
    return True

def action_problem_checker_recompile( id ):
    if wolf.problem_get(id) is None:
        return False;
    data.create("problem.checker.recompile", [id])
    return True
def action_problem_checker_set( id, name, source, compiler ):
    if id < 0 or id >= wolf.problem_count():
        return False
    if wolf.compiler_get(compiler) is None:
        return False
    source = data.save(base64.b64decode(source.encode('ascii')), name)
    data.create("problem.checker.set", [id, source, compiler])
    return True
def action_problem_checker_source( id ):
    if id < 0 or id >= wolf.problem_count():
        return False
    checker = wolf.problem_get(id).checker
    if checker is None:
        return None
    source = wolf.content_get(checker.source)
    return base64.b64encode(source.load()).decode('ascii')
def action_problem_create( name, full ):
    id = wolf.problem_count()
    data.create("problem.create", [id, name, full])
    return id
def action_problem_info( id ):
    if isinstance(id, list):
        return [action_problem_info(x) for x in id]
    if not isinstance(id, int):
        return False
    problem = wolf.problem_get(id)
    if problem is None:
        return False
    # todo: return status of problem
    return {
        'name': problem.name, 'full': problem.full,
        'input': problem.input, 'output': problem.output,
        'time_limit': problem.time_limit, 'memory_limit': problem.memory_limit,
        'tests': len(problem.tests)
    }
def action_problem_files_set( id, input, output ):
    if wolf.problem_get(id) is None:
        return False
    data.create("problem.files.set", [id, input, output])
    return True
def action_problem_limits_set( id, time, memory ):
    if id < 0 or id >= wolf.problem_count():
        return False
    data.create("problem.limits.set", [id, time, memory])
    return True
def action_problem_modify( id, name, full ):
    if not isinstance(id, int) or not isinstance(name, str) or not isinstance(full, str):
        return False
    problem = wolf.problem_get(id)
    if problem is None:
        return False
    data.create("problem.modify", [id, name, full])
    return True
def action_problem_test_add( id, test, answer ):
    if id < 0 or id >= wolf.problem_count():
        return False
    test = data.save(base64.b64decode(test.encode('ascii')))
    answer = data.save(base64.b64decode(answer.encode('ascii')))
    data.create('problem.test.add', [id, test, answer])
    return True
def action_problem_test_count( id ):
    if id < 0 or id >= wolf.problem_count():
        return False
    return len(wolf.problem_get(id).tests)

def action_submit( problem, name, source, compiler ):
    if problem < 0 or problem >= wolf.problem_count():
        return False
    if wolf.compiler_get(compiler) is None:
        return False
    source = data.save(base64.b64decode(source.encode('ascii')), name)
    id = wolf.submit_count()
    data.create('submit', [id, problem, source, compiler])
    return id
def action_submit_info( id ):
    if isinstance(id, list):
        return [action_submit_info(x) for x in id]
    if not isinstance(id, int):
        return False
    submit = wolf.submit_get(id)
    if submit is None:
        return False
    data = {'id': id, 'problem': submit.problem, 'status': 'Waiting', 'time': submit.time}
    if submit.binary is not None:
       data['status'] = 'Running'
    if submit.result is not None:
       data['status'] = 'Result'
       result, test = submit.result if submit.result is not None else (None, None)
       data['result'] = result
       data['test'] = test
    return data
def action_submit_report( id ):
    if isinstance(id, list):
        return [action_submit_report(x) for x in id]
    if not isinstance(id, int):
        return False
    submit = wolf.submit_get(id)
    if submit is None:
        return False
    if submit.binary is None:
        return False
    if submit.compiler_output is not None:
        compiler_output = wolf.content_get(submit.compiler_output).load()
    else:
        compiler_output = b''
    return {'compiler_output': base64.b64encode(compiler_output).decode('ascii')}
def action_submit_source( id ):
    if isinstance(id, list):
        return [action_submit_source(x) for x in id]
    if not isinstance(id, int):
        return False
    submit = wolf.submit_get(id)
    if submit is None:
        return False
    source = wolf.content_get(submit.source).load()
    return base64.b64encode(source).decode('ascii')
#def action_submit_status( id ):
#    if isinstance(id, list):
#        return [action_submit_status(x) for x in id]
#    submit = wolf.submit_get(id)
#    if submit is None:
#        return False
#    status, test = submit.result if submit.result is not None else (None, None)
#    return {'status': status, 'test': test}

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

net_actions = {
    'ping': lambda data: True,
    'archive.add': action_create(['problem'], action_archive_add),
    'archive.compiler.add': action_create(['id', 'name'], action_archive_compiler_add),
    'archive.compiler.list': action_create([], action_archive_compiler_list),
    'archive.compiler.remove': action_create(['id'], action_archive_compiler_remove),
    'archive.count': action_create([], action_archive_count),
    'archive.list': action_create(['start', 'limit'], action_archive_list),
    'archive.remove': action_create(['id'], action_archive_remove),
    'archive.submit': action_create(['team', 'problem', 'name', 'source', 'compiler'], action_archive_submit),
    'archive.submits': action_create(['team', 'problem', 'start', 'limit'], action_archive_submits, default=True),
    'compiler.add': action_create(['id', 'binary', 'compile', 'run'], action_compiler_add),
    'compiler.info': action_create(['id'], action_compiler_info),
    'compiler.list': action_create([], action_compiler_list),
    'compiler.modify': action_create(['id', 'binary', 'compile', 'run'], action_compiler_modify),
    'compiler.remove': action_create(['id'], action_compiler_remove),
    # 'problem.checker.default':
    'problem.checker.recompile': action_create(["id"], action_problem_checker_recompile),
    'problem.checker.set': action_create(["id", "name", "source", "compiler"], action_problem_checker_set),
    'problem.checker.source': action_create(["id"], action_problem_checker_source),
    'problem.create': action_create(['name', 'full'], action_problem_create),
    'problem.info': action_create(['id'], action_problem_info),
    'problem.files.set': action_create(['id', 'input', 'output'], action_problem_files_set),
    'problem.limits.set': action_create(['id', 'time', 'memory'], action_problem_limits_set),
    'problem.test.add': action_create(['id', 'test', 'answer'], action_problem_test_add),
    'problem.test.count': action_create(['id'], action_problem_test_count),
    #'problem.test.insert':
    #'problem.test.remove':
    'submit': action_create(['problem', 'name', 'source', 'compiler'], action_submit),
    'submit.info': action_create(['id'], action_submit_info),
    'submit.report': action_create(['id'], action_submit_report),
    'submit.source': action_create(['id'], action_submit_source),
    # removed: 'submit.status': action_create(['id'], action_submit_status),
    'team.add': action_create(['login', 'name', 'password'], action_team_add),
    'team.info': action_create(['login'], action_team_info),
    'team.login': action_create(['login', 'password'], action_team_login)
}

def problem_add( message ):
    log("ERROR: %s" % message)
    problems.push(message)

def judge_ready( judge ):
    result = [] if free_judges or not judge_queue else [(judge_check_queue, ())]
    free_judges.push(judge)
    return result

def judge_check_queue():
    while free_judges and judge_queue:
        action, parameters = judge_queue.pop()
        action(*parameters)
    return []

def action_checker_compile( id ):
    problem = wolf.problem_get(id)
    checker = problem.checker
    if checker is None:
        return problem_add("tried to compile undefined checker for problem #%d" % id)
    if checker.binary is not None:
        return
    compiler = wolf.compiler_get(checker.compiler)
    if compiler is None:
        # todo: add actions into list of bad compilers
        return problem_add("compiler %s doesn't exist, needed for checker in problem #%d" % (checker.compiler, id))
    if compiler.binary is None and compiler.compile is None:
        # interpretator, no need for compile
        checker.binary = checker.source
        return
    judge = judge_get()
    if judge is None:
        judge_queue.push((action_checker_compile, (id,)))
        return
    problem.checker.binary = False
    source = wolf.content_get(checker.source)
    binary_name = magic_parse(compiler.binary, {'name': source.name})
    command = magic_parse(compiler.compile, {'name': source.name, 'binary': binary_name})
    log("[re]compile checker for problem #%d (%s → %s)" % (id, source.name, binary_name))
    def callback( result, binary, output ):
        if result is Judge.OK:
            log("compile successful, size = %d, output = \n%s" % (len(binary), output.decode('iso8859-1')))
            binary = data.save(binary, binary_name)
            output = data.save(output)
            data.create("problem.checker.compiled", [id, binary, output])
            return []
        else:
            log("failed to compile checker for problem #%d:\n%s" % (id, output.decode('iso8859-1')))
            return []
    judge.compile(command, source, binary_name, callback)

def action_submit_compile( id ):
    submit = wolf.submit_get(id)
    if submit.binary is not None:
        return
    problem = wolf.problem_get(submit.problem)
    if problem is None or problem.checker is None or problem.checker.binary is None:
        # todo: move submit into queue if problem is not ready
        return problem_add("failed to test submit #%d: problem #%d doesn't exists or isn't ready" % (id, submit.problem))
    compiler = wolf.compiler_get(submit.compiler)
    if compiler is None:
        return problem_add("failed to compile submit #%d: compiler not exists: %s" % (id, submit.compiler))
    if compiler.binary is None and compiler.compile is None:
        # interpretator, no need for compile
        submit.binary = submit.source
        submit.compiler_output = None
        wolf.force_submit_test(id)
        return
    judge = judge_get()
    if judge is None:
        judge_queue.push((action_submit_compile, (id,)))
        return
    source = wolf.content_get(submit.source)
    binary_name = magic_parse(compiler.binary, {'name': source.name})
    command = magic_parse(compiler.compile, {'name': source.name, 'binary': binary_name})
    def callback( result, binary, output ):
        if result is Judge.OK:
            log("submit #%d compiled, size = %d, output:\n%s" % (id, len(binary), output.decode('iso8859-1')))
            binary = data.save(binary, binary_name)
            output = data.save(output)
            data.create('submit.compiled', [id, binary, output])
        elif result is Judge.CE:
            log("submit #%d: compilation error, output:\n%s" % (id, output.decode('iso8859-1')))
            output = data.save(output)
            data.create('submit.compiled', [id, '', output])
        else:
            problem_add("failed to compile submit #%d" % id)
        return []
    judge.compile(command, source, binary_name, callback)

def action_submit_test( id, test_no ):
    submit = wolf.submit_get(id)
    if submit.result is not None or submit.tests[test_no].status is not None:
        return
    assert 0 <= test_no < len(submit.tests)
    problem = wolf.problem_get(submit.problem)
    checker = problem.checker
    checker_binary = wolf.content_get(checker.binary)
    submit_compiler = wolf.compiler_get(submit.compiler)
    checker_compiler = wolf.compiler_get(checker.compiler)
    if submit_compiler is None:
        return problem_add("failed to compile submit #%d: compiler not exists: %s" % (id, submit.compiler))
    if checker_compiler is None:
        return problem_add("failed to compile submit #%d: compiler not exists: %s" % (id, checker.compiler))
    judge = judge_get()
    if judge is None:
        judge_queue.push((action_submit_test, (id, test_no)))
        return
    if submit_compiler.run is not None and submit_compiler.run == "$binary":
        log("WARNING: compiler %s has deprecated run string" % submit.compiler)
    if checker_compiler.run is not None and checker_compiler.run == "$binary":
        log("WARNING: compiler %s has deprecated run string" % checker.compiler)
    test = submit.tests[test_no]
    submit_binary = wolf.content_get(submit.binary)
    submit_source = wolf.content_get(submit.source)
    checker_source = wolf.content_get(checker.source)
    binary = wolf.content_get(submit.binary)
    if submit_compiler.run is None or submit_compiler.run == "$binary":
        submit_run = None
    else:
        submit_run = magic_parse(submit_compiler.run, {'name': submit_source.name, 'binary': submit_binary.name})
    if checker_compiler.run is None or checker_compiler.run == "$binary":
        checker_run = None
    else:
        checker_run = magic_parse(checker_compiler.run, {'name': checker_source.name, 'binary': checker_binary.name})
    data_test = wolf.content_get(test.test)
    data_answer = wolf.content_get(test.answer)
    def callback( status, maxtime, maxmemory, output ):
        log("submit #%d result on test #%d: %s" % (id, test_no, Judge.status_str[status]))
        if len(output) > 0:
            log(output.decode('iso8859-1'))
        data.create('submit.test', [id, test_no, Judge.status_str[status], maxtime, maxmemory])
        return []
    # todo: use compiler 'run' command
    judge.test(
        binary = submit_binary,
        run = submit_run,
        test = data_test,
        answer = data_answer,
        input = problem.input,
        output = problem.output,
        time_limit = problem.time_limit,
        memory_limit = problem.memory_limit,
        checker = checker_binary,
        checker_run = checker_run,
        callback = callback
    )

judge_get = lambda: free_judges.pop() if free_judges else None

def replay_wolf( timestamp, parameters ):
    global wolf, data
    wolf = core.Wolf(timestamp, shedulers, data)
    data.replayers = wolf.replayers()

replayers = {
    'wolf': replay_wolf
}

wolf = None

free_judges = Queue()
judge_queue = Queue()

actions = Queue()

problems = Queue()

shedulers = {
    'checker_compile': lambda id: actions.push((action_checker_compile, (id,))),
    'solution_compile': lambda id: actions.push((action_submit_compile, (id,))),
    'solution_test': lambda id, test: actions.push((action_submit_test, (id, test)))
}

data = data.Data(replayers, args.data + '.bin', args.data + ".log")
data.start()

sys.stdout.flush()
while True:
    while actions:
        action, arguments = actions.pop()
        action(*arguments)
    queue = poll() # Вместе вырвем себе мозг?
    for action, arguments in queue:
        queue.extend(action(*arguments))

