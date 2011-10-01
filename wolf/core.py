from .common import log

class Problem:
    def __init__( self, name, full ):
        self.name, self.full = name, full
        self.checker = None
        self.tests = []
        self.time_limit = None
        self.memory_limit = None

class Checker:
    def __init__( self, name, source, compiler ):
        self.name, self.source, self.compiler = name, source, compiler
        self.binary = None

class Compiler:
    def __init__( self, id, binary, compile, run ):
        self.id, self.binary, self.compile, self.run = id, binary, compile, run

class Team:
    def __init__( self, login, name, password ):
        self.login, self.name, self.password = login, name, password

class Wolf:
    def __init__( self, timestamp, judge_queue, problem_checker_compile ):
        self.__timestamp = timestamp
        self.__queue = judge_queue
        self.__compilers = {}
        self.__problems = []
        self.__teams = {}
        self.__problem_checker_compile = problem_checker_compile

    def replayers( self ):
        return {
            'compiler.add': self.replay_compiler_add,
            'compiler.remove': self.replay_compiler_remove,
            'problem.checker.set': self.replay_problem_checker_set,
            'problem.checker.compiled': self.replay_problem_checker_compiled,
            'problem.create': self.replay_problem_create,
            'problem.limits.set': self.replay_problem_limits_set,
            'problem.test.add': self.replay_problem_test_add,
            'team.add': self.replay_team_add
        }

    def replay_compiler_add( self, timestamp, parameters ):
        id, binary, compile, run = parameters
        self.__compilers[id] = Compiler(id, binary, compile, run)
    def replay_compiler_remove( self, timestamp, parameters ):
        id = parameters[0]
        del self.__compilers[id]
    def replay_problem_checker_set( self, timestamp, parameters ):
        id, name, source, compiler = parameters
        id = int(id)
        self.__problems[id].checker = Checker(name, source, compiler)
        self.__queue.push((self.__problem_checker_compile, [id]))
    def replay_problem_checker_compiled( self, timestamp, parameters ):
        id, binary, output = parameters
        id = int(id)
        assert self.__problems[id].checker is not None
        self.__problems[id].checker.binary = binary
    def replay_problem_create( self, timestamp, parameters ):
        id, name, full = parameters
        assert len(self.__problems) == int(id)
        self.__problems.append(Problem(name, full))
    def replay_problem_limits_set( self, timestamp, parameters ):
        id, time, memory = parameters
        id, time, memory = int(id), float(time), int(memory)
        self.__problems[id].time_limit = time
        self.__problems[id].memory_limit = memory
    def replay_problem_test_add( self, timestamp, parameters ):
        id, test, answer = parameters
        id = int(id)
        self.__problems[id].tests.append((test, answer))
    def replay_team_add( self, timestamp, parameters ):
        login, name, password = parameters
        self.__teams[login] = Team(login, name, password)

    def compiler_get( self, id ):
        return self.__compilers[id] if id in self.__compilers else None
    def compiler_list( self ):
        return sorted(self.__compilers.keys())
    def problem_count( self ):
        return len(self.__problems)
    def problem_get( self, id ):
        return self.__problems[id]
    def team_get( self, login ):
        return self.__teams[login] if login in self.__teams else None

