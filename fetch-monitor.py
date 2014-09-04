#!/usr/bin/env python3

import socket, sys

from dts import config
from dts.protocol import Packet, PacketParser

host, port, team, password, contest = sys.argv[1:]
port = int(port)

s = socket.socket()
s.connect((host, port))

s.send(Packet({
    'Team': team,
    'Password': password,
    'ContestId': contest
})())

parser = PacketParser(binary=True)
packets = False
while not packets:
    data = s.recv(4096)
    parser.add(data)
    packets = parser()

packet = packets[0]
if b'Error' in packet:
    print('testsys returned error:', packet[b'Error'].decode('ascii'))
    sys.exit(1)

with open('/dev/stdout', 'wb') as f:
    f.write(packet[b'Monitor'])
    f.write(b'\x1a\n')
    f.write(packet[b'History'])

