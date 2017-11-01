#!/usr/bin/env python3

import argparse, select, socket, sys, termios, time
from dts import config
from dts.protocol import Packet, PacketParser

class Console:
    NORMAL, LOCK, WAIT = range(3)
    def __init__( self, tab, command ):
        self.state = Console.NORMAL
        self.value = None
        self.__line = ''
        self.__message = ''
        self.__buffer = ''
        self.__tab = tab
        self.__command = command
        self.__start = 0
        self.__cursor = 0
        self.__width = 80
        # TODO: calculate width using termios and renew it using SIGWINCH
        self.__history = []
        self.__current = [x for x in self.__history] + [self.__line]
        self.__position = len(self.__history)
        self.__input = None

    def __enter( self ):
        if not self.__line:
            return
        self.__command(self.__line)
        if self.__line in self.__history:
            self.__history.remove(self.__line)
        self.__history.append(self.__line)
        if len(self.__history) > 100:
            del self.__history[0]
        self.__line = ''
        self.__cursor = 0
        self.__current = [x for x in self.__history] + [self.__line]
        self.__position = len(self.__history)

    def lock( self, message, value ):
        self.value = value
        self.state = Console.LOCK
        self.__message = message
        print('\r\033[K' + self.__message, end='')
    def unlock( self, message, wait=True ):
        self.state = Console.WAIT if wait else Console.NORMAL
        self.__message = message
        print('\r\033[K' + self.__message, end='')
        if not wait:
            self.write(self.__buffer)
            self.__buffer = ''
            self.redraw ()

    def write( self, text, force = False ):
        if len(text) != 0 and text[-1] != '\n':
            text += '%\n' # zsh style
        if self.state is Console.LOCK or force:
            print('\r\033[K' + text + self.__message, end='')
        elif self.state is Console.WAIT:
            self.__buffer += text
        else:
            print('\r\033[K' + text, end='')
            self.redraw()
        sys.stdout.flush()

    def redraw( self ):
        assert self.state is Console.NORMAL
        if self.__cursor < self.__start:
            self.__start = self.__cursor
        if self.__cursor - self.__start + 2 >= self.__width:
            self.__start = self.__cursor + 3 - self.__width
        if self.__cursor != len(self.__line) and self.__cursor - self.__start + 3 == self.__width:
            self.__start += 1
        start = '\033[1m<\033[0m' if self.__start != 0 else ' '
        finish = '\033[1m>\033[0m' if self.__start + self.__width - 2 < max(len(self.__line), self.__cursor + 1) else ''
        visual = self.__line[self.__start:self.__start + self.__width - (3 if finish != '' else 2)]
        move = self.__start + len(visual) + (1 if finish != '' else 0) - self.__cursor
        print('\r\033[K>' + start + visual + finish + ('\033[%dD' % move if move != 0 else ''), end='')

    def add( self, text ):
        if self.state is Console.LOCK:
            return
        for key in text:
            # TODO: setup keys for different terminals
            if self.__input is not None:
                self.__input += key
                if self.__input == "[A":
                    if self.__position != 0:
                        self.__current[self.__position] = self.__line
                        self.__position -= 1
                        self.__line = self.__current[self.__position]
                        self.__cursor = len(self.__line)
                        self.__start = 0
                elif self.__input == "[B":
                    if self.__position != len(self.__history):
                        self.__current[self.__position] = self.__line
                        self.__position += 1
                        self.__line = self.__current[self.__position]
                        self.__cursor = len(self.__line)
                        self.__start = 0
                elif self.__input == "[C":
                    self.__cursor = min(len(self.__line), self.__cursor + 1)
                elif self.__input == "[D":
                    self.__cursor = max(0, self.__cursor - 1)
                elif self.__input == "[1;5C":
                    pass # Ctrl+←
                elif self.__input == "[1;5D":
                    pass # Ctrl+→
                elif self.__input == "[1~":
                    self.__cursor = 0
                elif self.__input == "[3~":
                    self.__line = self.__line[0:self.__cursor] + self.__line[self.__cursor + 1:]
                elif self.__input == "[4~":
                    self.__cursor = len(self.__line)
                elif len(self.__input) > 5:
                    self.write("[debug] unknown escape sequence: \e%s\n" % self.__input)
                else:
                    continue
                self.__input = None
                continue
            if self.state is Console.WAIT:
                self.state = Console.NORMAL
                self.write(self.__buffer)
                self.__buffer = ''
                continue
            if ord(key) >= 0x20 and ord(key) != 0x7f:
                self.__line = self.__line[0:self.__cursor] + key + self.__line[self.__cursor:]
                self.__cursor += 1
            elif ord(key) == 0x09:
                bonus, result = self.__tab(self.__line[0:self.__cursor])
                if bonus:
                    result += ' '
                if result is not None:
                    self.__line = result + self.__line[self.__cursor:]
                    self.__cursor = len(result)
            elif ord(key) == 0x0a:
                self.__enter()
            elif ord(key) == 0x23:
                pass # Ctrl+W
            elif ord(key) == 0x7f:
                if self.__cursor == 0:
                    continue;
                self.__cursor -= 1
                self.__line = self.__line[0:self.__cursor] + self.__line[self.__cursor + 1:]
            elif ord(key) == 0x1b:
                self.__input = ''
            else:
                global count
                count += 1
                self.write("[debug] count = %d, key=%d\n" % (count, ord(key)), force=True)
        self.redraw()

def tab( line ):
    # TODO: optimize with prefix tree
    commands = config.commands
    targets = sorted([x for x in commands if x.startswith(line)])
    if len(targets) == 0:
        return (False, None)
    if len(targets) == 1:
        return (True, targets[0])
    index = 0
    while index < len(targets[0]) and index < len(targets[1]) and targets[0][index] == targets[1][index]:
        index += 1
    if index > len(line):
        return (False, targets[0][0:index])
    console.write(' '.join(targets) + '\n')
    return (False, None)

def console_command( line ):
    queue.append((command, line))

def command( line ):
    global command_id
    packet_id = "id_%08d" % command_id
    command_id += 1
    console.lock("*** waiting for testsys answer ***", packet_id)
    s.send(Packet({'ID': packet_id, 'Command': line})())

parser = argparse.ArgumentParser(description="Text console for testsys.")
parser.add_argument('--password-file', '-p', action='store', dest='key_file', required=True)
parser.add_argument('--name', '-n', action='store', dest='name', help='Displayed name.')
parser.add_argument('--contest', '-c', action='store', dest='contest', help='Select contest.')
parser.add_argument('--msglevel', '-m', action='store', dest='msglevel', help='Initial testsys verbosity level.')
parser.add_argument('server', metavar='<host>:<port>', help='Address of testsys server.')
args = parser.parse_args()

fd = sys.stdin.fileno()
tty_attr_old = termios.tcgetattr(fd)
attributes = termios.tcgetattr(fd)
attributes[3] &= ~(termios.ECHO | termios.ICANON)
attributes[6][termios.VMIN] = 0
termios.tcsetattr(fd, termios.TCSADRAIN, attributes)

console = Console(tab, console_command)
console.lock('*** connecting to testsys ***', "id_pre0")
command_id = 0
reconnect_id = 0

with open(args.key_file, 'rb') as key_file:
    key = key_file.read().decode(config.encoding)
    assert len(key) == 256, "invalid key: should be 256 bytes length"
# TODO: default port 17240, or not
host, port = args.server.split(':')
port = int(port)

poll = select.epoll()
poll.register(sys.stdin, select.EPOLLIN)

try:
    s = socket.socket()
    poll.register(s, select.EPOLLIN)
    s.connect((host, port))
    s.send(Packet({'Password': key, 'Command': "ver", 'ID': "id_pre0"})())
    if args.msglevel is not None:
        console.value = "id_pre1"
        s.send(Packet({'Command': "msg_level " + args.msglevel, 'ID': "id_pre1"})())
    if args.name is not None:
        console.value = "id_pre2"
        s.send(Packet({'Command': "name " + args.name, 'ID': "id_pre2"})())
    if args.contest is not None:
        console.value = "id_pre3"
        s.send (Packet ({'Command': "select_contest " + args.contest, 'ID': "id_pre3"})())
except KeyboardInterrupt:
    console.lock("terminated by KeyboardInterrupt", "never")
    print("");
    termios.tcsetattr(fd, termios.TCSADRAIN, tty_attr_old)
    sys.exit(1)

def reconnect():
    global reconnect_id, is_reconnect, s
    is_reconnect = True
    packet_id = "reconnect%d" % reconnect_id
    console.lock("*** reconnecting ***", packet_id + "_2")
    reconnect_id += 1
    del action[s.fileno()]
    try:
        poll.unregister(s)
        s.close()
        time.sleep(1)
        s = socket.socket()
        poll.register(s, select.EPOLLIN)
        action[s.fileno()] = handle_socket
        console.write("", force=True)
        s.connect((host, port))
        s.send(Packet({'Password': key, 'Command': "ver", 'ID': packet_id + "_0"})())
        if args.msglevel is not None:
            s.send(Packet({'Command': "msg_level " + args.msglevel, 'ID': packet_id + "_1"})())
        if args.name is not None:
            s.send(Packet({'Command': "name " + args.name, 'ID': packet_id + "_2"})())
        if args.contest is not None:
            s.send(Packet({'Command': "select_contest " + args.contest, 'ID': packet_id + "_3"})())
    except IOError as e:
        console.write("\033[31;1mexception while reconnecting: " + str(e) + "\033[0m\n")
        queue.append((reconnect, ()))

def handle_socket( handle, events ):
    if events & select.EPOLLIN:
        events &= ~select.EPOLLIN
        try:
            parser.add(s.recv(4096, socket.MSG_DONTWAIT))
            queue.append((handle_parser, ()))
        except IOError as e:
            console.write("\033[31;1mlost connection to testsys: recv: " + str(e) + "\033[0m\n", force=True)
            queue.append((reconnect, ()))
    if events & select.EPOLLERR:
        events &= ~select.EPOLLERR
        console.write("\033[31;1mlost connection to testsys: err\033[0m\n", force=True)
        queue.append((reconnect, ()))
    if events & select.EPOLLHUP:
        events &= ~select.EPOLLHUP
        console.write("\033[31;1mlost connection to testsys: hup\033[0m\n", force=True)
        queue.append((reconnect, ()))
    if events != 0:
        console.write("ERROR: cannot handle event %d (h=%d)\n" % (events, handle), force=True)
        count = 200

def handle_stdin( handle, events ):
    if events & select.EPOLLIN:
        events &= ~select.EPOLLIN
        console.add(sys.stdin.read(4096))
    if events != 0:
        console.write("ERROR: cannot handle event %d (h=%d)\n" % (events, handle), force=True)
        count = 4

def handle_parser():
    global is_reconnect
    for packet in parser():
        # console.write("[debug] work with packet %s\n" % str(packet))
        if 'Log' in packet:
            console.write(packet['Log'] + '\n')
        if 'Message' in packet:
            if packet['Message'] is not None:
                message = packet['Message']
                if message[-1] != '\n': message += '\n'
                console.write(message)
            else:
                console.write('\033[31;1mERROR: “Message” field exists in packet but is None.\033[0m\n')
        if 'Chat' in packet:
            console.write('\033[1m' + packet['Chat'] + '\033[0m\n')
        if 'ID' in packet:
            if console.state is Console.LOCK and console.value == packet['ID']:
                if is_reconnect:
                    console.unlock ('', wait=False)
                    is_reconnect = False
                else:
                    console.unlock('... press any key ...')
        # TODO: check for ignored keys

is_reconnect = False
action = {s.fileno() : handle_socket, sys.stdin.fileno(): handle_stdin}
parser = PacketParser()
count = 0
while True:
    queue = []
    # console.write("[debug] ready to poll\n", force=True)
    try:
        for handle, events in poll.poll():
            # console.write("[debug] poll: handle=%d, event_mask=%d (IN=%d,OUT=%d,ERR=%d)\n" % (handle, events, select.EPOLLIN, select.EPOLLOUT, select.EPOLLERR), force=True)
            if handle in action:
                queue.append((action[handle], (handle, events)))
            else:
                console.write("ERROR: cannot handle %d\n" % handle, force=True)
    except IOError as e:
        console.write("\033[31;1mERROR: " + str(e) + "\033[0m\n")
        queue.append((reconnect, ()))
    except KeyboardInterrupt:
        console.lock("terminated by KeyboardInterrupt", "never")
        print("");
        break
    except Exception:
        console.write("\033[31;1mERROR: " + str(e) + "\033[0m\n")
        break
    for f, p in queue:
        # console.write("[debug] next action\n")
        if isinstance(p, tuple):
            f(*p)
        else:
            f(p)
    # console.write("[debug] out of actions\n")
    if count > 10:
        break

termios.tcsetattr(fd, termios.TCSADRAIN, tty_attr_old)

#estSysConsoleTerminal::TestSysConsoleTerminal() : in(), console(), debug(), socket(), mutex(0), lock(), waitID(""), history(), counter(0)

#oid TestSysConsoleTerminal::exec( const String &name, String const &msglevel, const String &server, const String &keyFileName )
#
# File debugFile = File::openWrite("console_term.log");
# TerminalDevice debugConsole = TerminalDevice(console);
# debug.addOutput(debugFile, DEBUG_FULLLOGGING);
# debug.addOutput(debugConsole, DEBUG_EXTRADEBUG);
#
# bool exitFlag = false;
#
# tamias::MethodThread<TestSysConsoleTerminal> thread = tamias::MethodThread<TestSysConsoleTerminal>(this, &TestSysConsoleTerminal::secondLoop);
# while (true) {
#   try {
#     thread.create();
#     dts::PacketParser parser;
#     while (true) {
#       while (parser.packetReady())
#       {
#         Packet packet = parser.nextPacket();
#         for (sizetype i = 0; i < packet.values().size(); i++)
#         {
#           String packetName = escapeString(String::fromUtf8(Packet::ibm8662utf8(packet.values()[i].first)));
#           String packetValue = escapeString(String::fromUtf8(Packet::ibm8662utf8(packet.values()[i].second)));
#           debug.output(DEBUG_FULLLOGGING, "  “%s” = “%s”") << packetName << packetValue;
#         }
#         for (sizetype i = 0; i < packet.values().size(); i++)
#         {
#           String packetName = String::fromUtf8(Packet::ibm8662utf8(packet.values()[i].first));
#           String packetValue = String::fromUtf8(Packet::ibm8662utf8(packet.values()[i].second));
#           else if (packetName != "")
#           {
#             // lock.lock();
#             debug.output(DEBUG_DIAGNOSTIC, "unknow field in packet: “%s” -> “%s”") << packetName << packetValue; // TODO: semaphore!!!
#             // lock.unlock();
#           }
#         }
#       }
#     }
#     // lock.lock();
#     thread.cancel();
#     // lock.unlock();
#     console.setInput(" *** disconnected ***", 0);
#     socket.disconnect();
#     if (exitFlag)
#       break;
#     tamias::Thread::sleep(1);
#   } catch (tamias::Exception &e ) {
#     debug.output(DEBUG_INFORMATION, "exception!");
#     socket.disconnect();
#   }
# }
#
#
#tring TestSysConsoleTerminal::readCommand()
#
# Vector <Pair <String, sizetype> > currentHistory;
# for (sizetype i = 0; i < history.size(); i++)
#   currentHistory.pushBack(makePair(history[i], history[i].length()));
# sizetype historyIndex = currentHistory.size();
# currentHistory.pushBack(makePair(String(""), 0));
#/  String command = "";
#/  sizetype cursor = 0;
# while (true)
# {
#   String &command = currentHistory[historyIndex].first;
#   sizetype &cursor = currentHistory[historyIndex].second;
#   // lock.lock();
#   console.setInput("> " + command, cursor + 2);
#   // lock.unlock();
#   int key = in.nextKey();
#   switch (key)
#   {
#     case TerminalReader::KEY_UP:
#       if (historyIndex > 0)
#         historyIndex--;
#       break;
#     case TerminalReader::KEY_DOWN:
#       if (historyIndex < currentHistory.size() - 1)
#         historyIndex++;
#       break;
#     case TerminalReader::KEY_LEFT:
#     case TerminalReader::KEY_RIGHT:
#     case TerminalReader::KEY_HOME:
#     case TerminalReader::KEY_END:
#     case TerminalReader::KEY_BACKSPACE:
#     case TerminalReader::KEY_BACKSPACE2:
#     case TerminalReader::KEY_TAB:
#     case TerminalReader::KEY_DELETE:
#     case TerminalReader::KEY_ENTER:
#       // lock.lock();
#       console.setInput("", 0);
#       console.output("> " + command + "\n");
#       // lock.unlock();
#       return command;
#     default:
#   }
# }
#
#
#oid TestSysConsoleTerminal::secondLoop()
#
# while (true)
# {
#   String command = readCommand();
#/    bool was = false;
#/    for (sizetype i = 0; i < history.size(); i++)
#/      if (history[i] == command)
#/        was = true, i = history.size();
#/  TODO: better ignore dups
#   if (history.size() == 0 || history[history.size() - 1] != command)
#     history.pushBack(command);
#/ TODO:     while (history.size() >= 100)
#/    {
#/      for (sizetype i = 1; i < history.size(); i++)
#/        history[i - 1] = history[i];
#/      history.popBack();
#/    }
#   // lock.lock();
#   console.setInput(" --- waiting for testsys outcome ---", 0);
#   // lock.unlock();
#   // TODO: exit by Ctrl+D
#   String id = tamias::Format::intToString(counter++);
#   while (id.length() < 8) id = '0' + id; id = "id_" + id;
#   Packet packet;
#   packet.addValue("Command", Packet::utf82ibm866(command.toUtf8()));
#   packet.addValue("ID", id.toUtf8());
#   // lock.lock();
#   waitID = id;
#   mutex.set(1);
#   socket.write(packet.result());
#   // lock.unlock();
#   mutex.wait(1);
#   // lock.lock();
#   console.setInput(" --- press any key ---", 0);
#   // lock.unlock();
#   in.nextKey();
#   mutex.set(0, true);
# }
#
#
#
#namespace dts {
#  class TestSysConsoleTerminal   {
#    public:
#      TestSysConsoleTerminal();
#      ~TestSysConsoleTerminal();
#      void exec( const tamias::String &name, tamias::String const &msglevel, const tamias::String &server, const tamias::String &keyFileName );
#
#    private:
#      enum DebugLevel {
#        DEBUG_NOLOGGING = 0,
#        DEBUG_FATAL = 1,
#        DEBUG_ERROR = 2,
#        DEBUG_WARNING = 3,
#        DEBUG_INFORMATION = 4,
#        DEBUG_DIAGNOSTIC = 5,
#        DEBUG_DEBUG = 6,
#        DEBUG_EXTRADEBUG = 7,
#        DEBUG_FULLLOGGING = 8
#      };
#
#      burunduk3::TerminalReader in;
#      burunduk3::TerminalConsole console;
#      tamias::wtf::DebugOutput debug;
#      tamias::TcpClientSocket socket;
#      tamias::Mutex mutex;
#      tamias::Semaphore lock;
#      tamias::String waitID;
#      tamias::Vector <tamias::String> history;
#      tamias::Vector <tamias::String> testsysCommands;
#      int counter;
#  
#      tamias::String readCommand();
#      tamias::String tabCompletion( const tamias::String &prefix );
#      void secondLoop();
#  
#      TestSysConsoleTerminal( const TestSysConsoleTerminal &termninal );
#      TestSysConsoleTerminal& operator = ( const TestSysConsoleTerminal &terminal );
#  };
#}
