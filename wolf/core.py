from .common import log

class Checker:
    def __init__( self, source, compiler ):
        self.source, self.compiler = source, compiler
        self.binary = None

class Compiler:
    def __init__( self, id, binary, compile, run ):
        self.id, self.binary, self.compile, self.run = id, binary, compile, run

class Content:
    def __init__( self, hash, name, time, start, size, data ):
        self.hash, self.name, self.time = hash, name, time
        self.__start, self.__size, self.__data = start, size, data
    def load( self ):
        return self.__data.load(self.__start, self.__size)

class Problem:
    def __init__( self, name, full ):
        self.name, self.full = name, full
        self.checker = None
        self.tests = []
        self.time_limit = None
        self.memory_limit = None
        self.input = None
        self.output = None

class Submit:
    def __init__( self, problem, source, compiler, tests ):
        self.problem, self.source, self.compiler = problem, source, compiler
        self.tests = [Test(*x) for x in tests]
        self.testings = {0}
        self.last_test = None
        self.result = None
        self.binary = None
    def tested( self, test, status, time, memory ):
        assert test in self.testings
        self.testings.remove(test)
        self.tests[test].result(status, time, memory)
        self.last_test = test
        if len(self.testings) == 0:
            test = self.last_test + 1
            if status == "OK" and test < len(self.tests):
                self.testings.add(test)
            else:
                if status == "OK":
                    self.last_test = None
                    status = "AC"
                self.result = (status, self.last_test)

class Team:
    def __init__( self, login, name, password ):
        self.login, self.name, self.password = login, name, password

class Test:
    def __init__( self, test, answer ):
        self.test, self.answer = test, answer
        self.status = None
        self.output = None
    def result( self, status, time_peak, memory_peak ):
        self.status, self.time_peak, self.memory_peak = status, time_peak, memory_peak

class Archive:
    def __init__( self ):
        self.problems = set()
        self.problem_list = []
        self.submits_all = []
        self.submits_team = {}
        self.submits_problem = {}
        self.submits = {}
        self.compilers = {}
    def add_problem( self, problem ):
        self.problems.add(problem)
        self.problem_list.append(problem)
    def add_submit( self, team, problem, id ):
        self.submits_all.append(id)
        if team not in self.submits_team:
            self.submits_team[team] = []
        self.submits_team[team].append(id)
        if problem not in self.submits_problem:
            self.submits_problem[problem] = []
        self.submits_problem[problem].append(id)
        if (team, problem) not in self.submits:
            self.submits[(team, problem)] = []
        self.submits[(team, problem)].append(id)

class Wolf:
    def __init__( self, timestamp, shedulers, data ):
        self.__timestamp = timestamp
        self.__shedulers = shedulers
        self.__compilers = {}
        self.__content = {}
        self.__problems = []
        self.__submits = []
        self.__teams = {}
        self.__data = data
        self.__archive = Archive()

    def replayers( self ):
        return {
            'archive.add': self.replay_archive_add,
            'archive.compiler.add': self.replay_archive_compiler_add,
            'archive.compiler.remove': self.replay_archive_compiler_remove,
            # 'archive.remove': self.replay_archive_remove,
            'archive.submit': self.replay_archive_submit,
            'compiler.add': self.replay_compiler_add,
            'compiler.remove': self.replay_compiler_remove,
            'content': self.replay_content,
            'problem.checker.compiled': self.replay_problem_checker_compiled,
            'problem.checker.recompile': self.replay_problem_checker_recompile,
            'problem.checker.set': self.replay_problem_checker_set,
            'problem.create': self.replay_problem_create,
            'problem.files.set': self.replay_problem_files_set,
            'problem.limits.set': self.replay_problem_limits_set,
            'problem.test.add': self.replay_problem_test_add,
            'submit': self.replay_submit,
            'submit.compiled': self.replay_submit_compiled,
            'submit.test': self.replay_submit_test,
            'team.add': self.replay_team_add
        }

    def replay_archive_add( self, timestamp, parameters ):
        problem_id = int(*parameters)
        assert problem_id not in self.__archive.problems and 0 <= problem_id < len(self.__problems)
        self.__archive.add_problem(problem_id)
    def replay_archive_compiler_add( self, timestamp, parameters ):
        compiler, name = parameters
        assert compiler not in self.__archive.compilers
        assert compiler in self.__compilers
        self.__archive.compilers[compiler] = name
    def replay_archive_compiler_remove( self, timestamp, parameters ):
        compiler = parameters[0]
        assert compiler in self.__archive.compilers
        del self.__archive.compilers[compiler]
    def replay_archive_submit( self, timestamp, parameters ):
        id, team, problem,  source, compiler = parameters
        id = int(id)
        assert len(self.__submits) == id
        problem = int(problem)
        assert problem in self.__archive.problems
        self.__archive.add_submit(team, problem, id)
        submit = Submit(problem, source, compiler, self.__problems[problem].tests)
        submit.origin = (None, team)
        self.__submits.append(submit)
        self.__shedulers['solution_compile'](int(id))
    def replay_compiler_add( self, timestamp, parameters ):
        id, binary, compile, run = parameters
        self.__compilers[id] = Compiler(id, binary, compile, run)
    def replay_compiler_remove( self, timestamp, parameters ):
        id = parameters[0]
        del self.__compilers[id]
    def replay_content( self, timestamp, parameters ):
        hash, name, start, size = parameters
        start = int(start)
        size = int(size)
        self.__content[hash] = Content(hash, name, timestamp, start, size, self.__data)
    def replay_problem_checker_compiled( self, timestamp, parameters ):
        id, binary, output = parameters
        id = int(id)
        assert self.__problems[id].checker is not None
        self.__problems[id].checker.binary = binary
    def replay_problem_checker_recompile( self, timestamp, parameters ):
        id = int(parameters[0])
        self.__problems[id].checker.binary = None
        self.__shedulers['checker_compile'](id)
    def replay_problem_checker_set( self, timestamp, parameters ):
        id, source, compiler = parameters
        id = int(id)
        self.__problems[id].checker = Checker(source, compiler)
        self.__shedulers['checker_compile'](id)
    def replay_problem_create( self, timestamp, parameters ):
        id, name, full = parameters
        assert len(self.__problems) == int(id)
        self.__problems.append(Problem(name, full))
    def replay_problem_files_set( self, timestamp, parameters ):
        id, input, output = parameters
        id = int(id)
        self.__problems[id].input = input
        self.__problems[id].output = output
    def replay_problem_limits_set( self, timestamp, parameters ):
        id, time, memory = parameters
        id, time, memory = int(id), float(time), int(memory)
        self.__problems[id].time_limit = time
        self.__problems[id].memory_limit = memory
    def replay_problem_test_add( self, timestamp, parameters ):
        id, test, answer = parameters
        id = int(id)
        self.__problems[id].tests.append((test, answer))
    def replay_submit( self, timestamp, parameters ):
        id, problem,  source, compiler = parameters
        assert len(self.__submits) == int(id)
        problem = int(problem)
        submit = Submit(problem, source, compiler, self.__problems[problem].tests)
        self.__submits.append(submit)
        self.__shedulers['solution_compile'](int(id))
    def replay_submit_compiled( self, timestamp, parameters ):
        id, binary, output = parameters
        id = int(id)
        self.__submits[id].binary = binary if binary != '' else False
        self.__submits[id].compiler_output = output
        if self.__submits[id].binary is not False:
            for test in self.__submits[id].testings:
                self.__shedulers['solution_test'](id, test)
        else:
            self.__submits[id].result = ('CE', None)
    def replay_submit_test( self, timestamp, parameters ):
        id, test, status, time_peak, memory_peak = parameters
        id = int(id)
        test = int(test)
        time_peak = float(time_peak)
        memory_peak = float(memory_peak)
        self.__submits[id].tested(test, status, time_peak, memory_peak)
        for test in self.__submits[id].testings:
            self.__shedulers['solution_test'](id, test)
    def replay_team_add( self, timestamp, parameters ):
        login, name, password = parameters
        self.__teams[login] = Team(login, name, password)

    def archive_get( self ):
        return self.__archive
    def compiler_get( self, id ):
        return self.__compilers.get(id)
    def compiler_list( self ):
        return sorted(self.__compilers.keys())
    def content_get( self, hash ):
        return self.__content.get(hash)
    def problem_count( self ):
        return len(self.__problems)
    def problem_get( self, id ):
        return self.__problems[id]
    def submit_count( self ):
        return len(self.__submits)
    def submit_get( self, id ):
        return self.__submits[id]
    def team_get( self, login ):
        return self.__teams.get(login)

