#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Require an isolated network namespace with working local TCP."""
import json
import socket
import subprocess


def validate_interfaces(interfaces):
    if len(interfaces) != 1 or interfaces[0].get('ifname') != 'lo':
        raise ValueError('offline test requires only the loopback interface')
    if 'UP' not in interfaces[0].get('flags', []):
        raise ValueError('loopback must be up for fakeroot TCP IPC')


def check_local_tcp():
    with socket.socket() as listener:
        listener.settimeout(2)
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        with socket.create_connection(listener.getsockname(), timeout=2) as client:
            connection, _ = listener.accept()
            with connection:
                connection.settimeout(2)
                client.sendall(b'x')
                if connection.recv(1) != b'x':
                    raise ValueError('local TCP exchange failed')


if __name__ == '__main__':
    validate_interfaces(json.loads(subprocess.check_output(['ip', '-j', 'link'])))
    check_local_tcp()
    print('Offline network verified: loopback TCP works; no external interface')
