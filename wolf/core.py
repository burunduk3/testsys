
class Team:
    def __init__( self, login, name, password ):
        self.login, self.name, self.password = login, name, password

class Compiler:
    def __init__( self, id, binary, compile, run ):
        self.id, self.binary, self.compile, self.run = id, binary, compile, run

class Wolf:
    def __init__( self, timestamp ):
        self.__timestamp = timestamp
        self.__teams = {}
        self.__compilers = {}

    def replayers( self ):
        return {
            'compiler.add': self.replay_compiler_add,
            'compiler.remove': self.replay_compiler_remove,
            'team.add': self.replay_team_add
        }

    def replay_compiler_add( self, timestamp, parameters ):
        id, binary, compile, run = parameters
        self.__compilers[id] = Compiler(id, binary, compile, run)
    def replay_compiler_remove( self, timestamp, parameters ):
        del self.__compilers[id]
    def replay_team_add( self, timestamp, parameters ):
        login, name, password = parameters
        self.__teams[login] = Team(login, name, password)

    def compiler_get( self, id ):
        return self.__compilers[id] if id in self.__compilers else None
    def compiler_list( self ):
        return sorted(self.__compilers.keys())
    def team_get( self, login ):
        return self.__teams[login] if login in self.__teams else None

