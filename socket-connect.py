#!/usr/bin/env python3

import socket, sys

if len(sys.argv) < 3:
    print("usage: %s <socket> <command> [<arguments>...]" % sys.argv[0])
    sys.exit(0)

s = socket.socket(socket.AF_UNIX)
s.connect(sys.argv[1])

s.send((' '.join(sys.argv[2:]) + '\n').encode('utf8'))
def read_all():
    while True:
        data = s.recv(1024)
        yield data
        if len(data) == 0 or b'\n' in data:
            break
print(b''.join(read_all()).decode('utf8'), end='')

s.close()

