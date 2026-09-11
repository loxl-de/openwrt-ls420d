#!/usr/bin/env python3
"""Build a deterministic data-only Buffalo companion; no network or compiler."""
import argparse
import base64
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import struct
from cpio_newc import Entry, encode, decode, wrap_ramdisk, unwrap_ramdisk

MAX_PAYLOAD = 1024 * 1024
FORMAT = 2
MARKER = 'etc/ls420d-deployment'
SITE_UCI = 'etc/ls420d-site.uci'

# Directories whose contents are credentials: 0700 for the directory and 0600
# for every file. Everything else is ordinary world-readable configuration.
SECRET_DIRS = ('etc/dropbear/', 'root/.ssh/')
SECRET_FILES = {'etc/shadow'}

PUBLIC_KEY_TYPES = ('ssh-ed25519',)
HOST_KEY_TYPES = ('ssh-ed25519',)
HOSTNAME = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?')


def ssh_type_prefix(name):
    return struct.pack('>I', len(name)) + name.encode()


def public_key_line(line, allowed=PUBLIC_KEY_TYPES):
    """Return 'type base64' for one authorized_keys line; strip the comment."""
    parts = line.split()
    if len(parts) < 2 or parts[0] not in allowed:
        raise ValueError('authorized key must be one of: %s' % ', '.join(allowed))
    blob = base64.b64decode(parts[1], validate=True)
    if not blob.startswith(ssh_type_prefix(parts[0])):
        raise ValueError('public key blob does not match its declared type')
    if parts[0] == 'ssh-ed25519' and (len(blob) != 51 or blob[15:19] != struct.pack('>I', 32)):
        raise ValueError('invalid Ed25519 public key encoding')
    # Strip the comment, which may contain a person's email or workstation.
    return parts[0] + ' ' + parts[1]


def check_host_key(data, allowed=HOST_KEY_TYPES):
    if len(data) < 64 or not any(data.startswith(ssh_type_prefix(t)) for t in allowed):
        raise ValueError('host key must be a Dropbear private key of type %s, not an OpenSSH key'
                         % ' or '.join(allowed))


def config_files(config, root, example=False):
    allowed = {'hostname', 'network'} | (set() if example else {'ssh_public_key', 'dropbear_host_key'})
    if set(config) != allowed:
        raise ValueError('unexpected or missing configuration fields')
    hostname = config['hostname']
    if not isinstance(hostname, str) or not HOSTNAME.fullmatch(hostname):
        raise ValueError('hostname must be a single DNS label')
    network = config['network']
    mode = network.get('mode')
    text = "config interface 'loopback'\n\toption device 'lo'\n\toption proto 'static'\n\toption ipaddr '127.0.0.1'\n\toption netmask '255.0.0.0'\n\nconfig interface 'lan'\n\toption device 'eth0'\n"
    if mode == 'dhcp' and set(network) == {'mode'}:
        text += "\toption proto 'dhcp'\n"
    elif mode == 'static' and set(network) <= {'mode', 'address', 'gateway', 'dns'}:
        interface = ipaddress.IPv4Interface(network['address'])
        text += "\toption proto 'static'\n\toption ipaddr '%s'\n\toption netmask '%s'\n" % (interface.ip, interface.netmask)
        if 'gateway' in network:
            gateway = ipaddress.IPv4Address(network['gateway'])
            if gateway not in interface.network:
                raise ValueError('gateway must be in the configured subnet')
            text += "\toption gateway '%s'\n" % gateway
        if not isinstance(network.get('dns', []), list):
            raise ValueError('dns must be an array of IPv4 addresses')
        for dns in network.get('dns', []):
            text += "\tlist dns '%s'\n" % ipaddress.IPv4Address(dns)
    else:
        raise ValueError('invalid network mode or fields')
    files = {
        'etc/config/network': text.encode(),
        # Merged by the generic image's uci-defaults hook after config_generate,
        # so the generated system defaults (LEDs, buttons, logging) survive.
        SITE_UCI: ("set system.@system[0].hostname='%s'\n" % hostname).encode(),
        'etc/config/dropbear': ("config dropbear 'main'\n\toption enable '%s'\n\toption Interface 'lan'\n\toption PasswordAuth 'off'\n\toption RootPasswordAuth 'off'\n\toption Port '22'\n" % ('0' if example else '1')).encode(),
        MARKER: (f'format={FORMAT}\nexample={int(example)}\nsource=json\nhostname={hostname}\n').encode(),
    }
    if not example:
        def input_file(name, private=False):
            value = config[name]
            if not isinstance(value, str) or not value:
                raise ValueError('key paths must be nonempty strings')
            path = root/value
            if path.is_symlink() or not path.is_file():
                raise ValueError('key must be a regular, non-symlink file')
            if private and path.stat().st_mode & 0o077:
                raise ValueError('private host key requires mode 0600 or stricter')
            if not 0 < path.stat().st_size <= 16384:
                raise ValueError('key file size outside bounds')
            return path.read_bytes()
        line = public_key_line(input_file('ssh_public_key').decode('ascii').strip(), ('ssh-ed25519',))
        files['etc/dropbear/authorized_keys'] = (line + '\n').encode()
        host_key = input_file('dropbear_host_key', private=True)
        check_host_key(host_key, ('ssh-ed25519',))
        files['etc/dropbear/dropbear_ed25519_host_key'] = host_key
    return files


def file_mode(name):
    if name in SECRET_FILES or name.startswith(SECRET_DIRS):
        return stat.S_IFREG | 0o600
    return stat.S_IFREG | 0o644


def entries_for(files):
    directories = {}
    for name in files:
        parts = name.split('/')
        for depth in range(1, len(parts)):
            directory = '/'.join(parts[:depth]) + '/'
            directories[directory.rstrip('/')] = stat.S_IFDIR | (0o700 if directory in SECRET_DIRS else 0o755)
    entries = [Entry(name, mode) for name, mode in sorted(directories.items())]
    entries += [Entry(name, file_mode(name), data) for name, data in sorted(files.items())]
    return entries


def build(files):
    entries = entries_for(files)
    payload = encode(entries)
    if len(payload) > MAX_PAYLOAD:
        raise ValueError('companion exceeds pilot memory budget')
    result = wrap_ramdisk(payload)
    if decode(unwrap_ramdisk(result))[0] != entries:
        raise ValueError('archive round-trip mismatch')
    return result


def image(config, root, example=False):
    return build(config_files(config, root, example))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--example', action='store_true', help='public, anonymous, SSH-disabled example')
    group.add_argument('--config', type=Path, help='private deployment JSON; key paths are relative to it')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config_path = args.config or Path(__file__).resolve().parents[1]/'examples/example.json'
    config = json.loads(config_path.read_text())
    result = image(config, config_path.parent, args.example)
    os.umask(0o077)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents accidentally replacing a known-good companion.
    with args.output.open('xb') as stream:
        stream.write(result)
    print(hashlib.sha256(result).hexdigest(), args.output.name)
    if not args.example:
        print('PRIVATE: contains a recoverable host key. Do not publish this image.')


if __name__ == '__main__':
    main()
