#!/usr/bin/env python3
"""Build a deterministic data-only Buffalo companion; no network or compiler."""
import argparse
import base64
import hashlib
import io
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import struct
import tarfile
from cpio_newc import Entry, encode, decode, wrap_ramdisk, unwrap_ramdisk

MAX_PAYLOAD = 1024 * 1024
MAX_MEMBER = 256 * 1024
FORMAT = 2
MARKER = 'etc/ls420d-deployment'
SITE_UCI = 'etc/ls420d-site.uci'

# Directories whose contents are credentials: 0700 for the directory and 0600
# for every file. Everything else is ordinary world-readable configuration.
SECRET_DIRS = ('etc/dropbear/', 'root/.ssh/')
SECRET_FILES = {'etc/shadow'}

# What a sysupgrade backup may contribute. Paths are relative, without './'.
BACKUP_DIRS = ('etc/config/', 'etc/dropbear/', 'etc/crontabs/', 'root/.ssh/')
BACKUP_FILES = {'etc/hosts', 'etc/passwd', 'etc/group', 'etc/shadow'}
BACKUP_IGNORED = {'etc/sysupgrade.conf', 'etc/inittab', 'etc/profile', 'etc/shells',
                  'etc/shinit', 'etc/sysctl.conf'}
PUBLIC_KEY_TYPES = ('ssh-ed25519', 'ssh-rsa', 'ecdsa-sha2-nistp256',
                    'ecdsa-sha2-nistp384', 'ecdsa-sha2-nistp521')
HOST_KEY_TYPES = ('ssh-ed25519', 'ssh-rsa')
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


# Exactly the spellings config_get_bool maps to false; anything else falls
# back to the default, which is ON for both Dropbear options. Case matters.
OFF_VALUES = ('0', 'off', 'false', 'no', 'disabled')
UCI_NAME = re.compile(r'[A-Za-z0-9_]+')


def uci_tokens(line):
    """Split one UCI line like libuci: single quotes verbatim, double quotes
    verbatim, whitespace separates. Backslash escapes and inline comments are
    refused rather than guessed at."""
    tokens = []
    i = 0
    while i < len(line):
        c = line[i]
        if c in ' \t':
            i += 1
            continue
        if c == '#':
            if tokens:
                raise ValueError('inline comments are not supported in companion UCI files')
            return []
        token = ''
        while i < len(line) and line[i] not in ' \t':
            c = line[i]
            if c in '\'"':
                j = line.find(c, i + 1)
                if j < 0:
                    raise ValueError('unterminated quote in UCI line')
                token += line[i + 1:j]
                i = j + 1
            elif c == '\\':
                raise ValueError('backslash escapes are not supported in companion UCI files')
            else:
                token += c
                i += 1
        if '\\' in token:
            raise ValueError('backslash escapes are not supported in companion UCI files')
        tokens.append(token)
    return tokens


def uci_sections(text, section_type):
    """Parse a UCI file into [(name, {option: value})]; later options override
    earlier ones as in libuci, list items accumulate space-separated as in the
    shell config loader. Unknown keywords or shapes are refused."""
    sections = []
    for number, line in enumerate(text.split('\n'), 1):
        if '\r' in line or '\0' in line:
            raise ValueError('control characters in UCI line %d' % number)
        tokens = uci_tokens(line)
        if not tokens:
            continue
        keyword = tokens[0]
        if keyword == 'config':
            if len(tokens) not in (2, 3) or not UCI_NAME.fullmatch(tokens[1]):
                raise ValueError('malformed section header in UCI line %d' % number)
            if tokens[1] != section_type:
                raise ValueError('only %s sections are allowed (UCI line %d)' % (section_type, number))
            if len(tokens) == 3 and not UCI_NAME.fullmatch(tokens[2]):
                raise ValueError('malformed section name in UCI line %d' % number)
            sections.append((tokens[2] if len(tokens) == 3 else None, {}))
        elif keyword in ('option', 'list'):
            if len(tokens) != 3 or not UCI_NAME.fullmatch(tokens[1]) or not sections:
                raise ValueError('malformed %s in UCI line %d' % (keyword, number))
            name, value = tokens[1], tokens[2]
            if keyword == 'list' and name in sections[-1][1]:
                value = sections[-1][1][name] + ' ' + value
            sections[-1][1][name] = value
        else:
            raise ValueError('unsupported UCI keyword %r in line %d' % (keyword, number))
    return sections


def check_dropbear_config(text):
    """Every dropbear section must switch password login off explicitly.

    Dropbear's init script defaults PasswordAuth and RootPasswordAuth to on
    when the option is absent or carries a value config_get_bool does not
    recognise, so only an exact off spelling counts. Each section is a
    separate SSH instance.
    """
    sections = uci_sections(text, 'dropbear')
    if not sections:
        raise ValueError('dropbear config has no dropbear section')
    for _, options in sections:
        for key in ('PasswordAuth', 'RootPasswordAuth'):
            if options.get(key) not in OFF_VALUES:
                raise ValueError('every dropbear section must set %s to one of %s; '
                                 'Dropbear defaults it to on otherwise' % (key, ', '.join(OFF_VALUES)))


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
        # One or more Ed25519 public keys, one per line; comments are stripped.
        lines = [public_key_line(line, ('ssh-ed25519',))
                 for line in input_file('ssh_public_key').decode('ascii').splitlines()
                 if line.strip() and not line.lstrip().startswith('#')]
        if not lines:
            raise ValueError('ssh_public_key contains no public key')
        files['etc/dropbear/authorized_keys'] = ''.join(line + '\n' for line in lines).encode()
        host_key = input_file('dropbear_host_key', private=True)
        check_host_key(host_key, ('ssh-ed25519',))
        files['etc/dropbear/dropbear_ed25519_host_key'] = host_key
    return files


def backup_member_name(info):
    name = info.name
    while name.startswith('./') or name.startswith('/'):
        name = name[2:] if name.startswith('./') else name[1:]
    if not name or any(part in ('', '.', '..') for part in name.split('/')):
        raise ValueError('unsafe path in backup archive')
    return name


def backup_files(data):
    """Select and validate the files of an OpenWrt sysupgrade backup."""
    files = {}
    hostname = ''
    try:
        archive = tarfile.open(fileobj=io.BytesIO(data), mode='r:*')
    except tarfile.TarError as error:
        raise ValueError('backup is not a readable tar archive') from error
    with archive:
        for info in archive:
            if info.isdir():
                continue
            name = backup_member_name(info)
            if not info.isfile():
                raise ValueError('backup member is not a regular file: %s' % name)
            if info.size > MAX_MEMBER:
                raise ValueError('backup member too large: %s' % name)
            content = archive.extractfile(info).read()
            if name in BACKUP_IGNORED:
                continue
            if name == 'etc/rc.local':
                lines = [l.strip() for l in content.decode('utf-8', 'replace').splitlines()]
                if [l for l in lines if l and not l.startswith('#')] in ([], ['exit 0']):
                    continue
                raise ValueError('etc/rc.local carries commands; the companion is data only')
            if name in BACKUP_FILES:
                pass
            elif name.startswith(BACKUP_DIRS):
                directory = next(d for d in BACKUP_DIRS if name.startswith(d))
                if '/' in name[len(directory):]:
                    raise ValueError('nested directory not allowed in backup: %s' % name)
            else:
                raise ValueError('path not allowed in a companion: %s' % name)
            if name in ('etc/dropbear/authorized_keys', 'root/.ssh/authorized_keys'):
                # Dropbear honours both files for root; validate both alike.
                lines = [public_key_line(l) for l in content.decode('ascii').splitlines()
                         if l.strip() and not l.lstrip().startswith('#')]
                content = ''.join(l + '\n' for l in lines).encode()
            elif name.startswith('etc/dropbear/'):
                if not re.fullmatch(r'dropbear_[a-z0-9]+_host_key', name[len('etc/dropbear/'):]):
                    raise ValueError('unexpected file in etc/dropbear: %s' % name)
                check_host_key(content)
            elif name == 'etc/config/dropbear':
                check_dropbear_config(content.decode('utf-8', 'replace'))
            elif name == 'etc/config/system':
                match = re.search(r"option\s+hostname\s+'([^']*)'", content.decode('utf-8', 'replace'))
                if match and HOSTNAME.fullmatch(match.group(1)):
                    hostname = match.group(1)
            elif name.startswith('etc/config/ls420d') or name == SITE_UCI:
                raise ValueError('reserved companion path in backup: %s' % name)
            if name.startswith('etc/config/') and not re.fullmatch(r'[A-Za-z0-9_-]+', name[len('etc/config/'):]):
                raise ValueError('not a UCI configuration name: %s' % name)
            if b'\0' in content and not name.startswith('etc/dropbear/') and not name.startswith('root/.ssh/'):
                raise ValueError('binary content in configuration file: %s' % name)
            files[name] = content
    if not files:
        raise ValueError('backup contains no usable configuration files')
    files[MARKER] = (f'format={FORMAT}\nexample=0\nsource=backup\nhostname={hostname}\n').encode()
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


def image_from_backup(data):
    return build(backup_files(data))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--example', action='store_true', help='public, anonymous, SSH-disabled example')
    group.add_argument('--config', type=Path, help='private deployment JSON; key paths are relative to it')
    group.add_argument('--backup', type=Path, help='private OpenWrt sysupgrade backup (sysupgrade -b) archive')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.backup:
        result = image_from_backup(args.backup.read_bytes())
    else:
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
