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


def config_files(config, root, example=False):
    allowed = {'hostname', 'network'} | (set() if example else {'ssh_public_key', 'dropbear_host_key'})
    if set(config) != allowed:
        raise ValueError('unexpected or missing configuration fields')
    hostname = config['hostname']
    if not isinstance(hostname, str) or not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', hostname):
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
        'etc/config/system': ("config system\n\toption hostname '%s'\n\toption timezone 'UTC'\n\nconfig timeserver 'ntp'\n\toption enabled '1'\n\tlist server '0.openwrt.pool.ntp.org'\n\tlist server '1.openwrt.pool.ntp.org'\n" % hostname).encode(),
        'etc/config/dropbear': ("config dropbear 'main'\n\toption enable '%s'\n\toption Interface 'lan'\n\toption PasswordAuth 'off'\n\toption RootPasswordAuth 'off'\n\toption Port '22'\n" % ('0' if example else '1')).encode(),
        'etc/ls420d-deployment': (f'format=1\nexample={int(example)}\nhostname={hostname}\n').encode(),
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
        authorized = []
        for line in input_file('ssh_public_key').decode('ascii').splitlines():
            parts = line.strip().split()
            if not parts:
                continue
            if len(parts) < 2 or parts[0] != 'ssh-ed25519':
                raise ValueError('supply Ed25519 OpenSSH PUBLIC keys, one per line')
            blob = base64.b64decode(parts[1], validate=True)
            if len(blob) != 51 or blob[:19] != struct.pack('>I', 11)+b'ssh-ed25519'+struct.pack('>I', 32):
                raise ValueError('invalid Ed25519 public key encoding')
            # Keep every distinct key, but omit potentially personal comments.
            normalized = parts[0]+' '+parts[1]
            if normalized not in authorized:
                authorized.append(normalized)
        if not authorized:
            raise ValueError('at least one Ed25519 public key is required')
        files['etc/dropbear/authorized_keys'] = ('\n'.join(authorized)+'\n').encode()
        host_key = input_file('dropbear_host_key', private=True)
        if len(host_key) < 64 or not host_key.startswith(struct.pack('>I', 11)+b'ssh-ed25519'):
            raise ValueError('host key must be a Dropbear Ed25519 private key, not an OpenSSH key')
        files['etc/dropbear/dropbear_ed25519_host_key'] = host_key
    return files


def image(config, root, example=False):
    files = config_files(config, root, example)
    entries = [Entry('etc', stat.S_IFDIR | 0o755), Entry('etc/config', stat.S_IFDIR | 0o755)]
    if not example:
        entries.append(Entry('etc/dropbear', stat.S_IFDIR | 0o700))
    entries += [Entry(name, stat.S_IFREG | 0o600, data) for name, data in sorted(files.items())]
    payload = encode(entries)
    if len(payload) > MAX_PAYLOAD:
        raise ValueError('companion exceeds pilot memory budget')
    result = wrap_ramdisk(payload)
    if decode(unwrap_ramdisk(result))[0] != entries:
        raise ValueError('archive round-trip mismatch')
    return result


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
