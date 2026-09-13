"""Optional single-job companion configuration; no archive import or shell input."""
import base64
import re
import struct
import uuid


def backup_files(job, root):
    fields = {'host', 'user', 'source', 'volume_uuid', 'hour', 'minute',
              'client_key', 'host_public_key'}
    if not isinstance(job, dict) or set(job) != fields:
        raise ValueError('backup requires exactly the documented job fields')
    host, user, source = (job[n] for n in ('host', 'user', 'source'))
    if not isinstance(host, str) or len(host) > 253 or not all(
            re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
            for label in host.split('.')):
        raise ValueError('backup host must be an IPv4 address or DNS name')
    if not isinstance(user, str) or not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', user):
        raise ValueError('invalid backup login name')
    if not isinstance(source, str) or not re.fullmatch(r'/[A-Za-z0-9_./-]{1,1023}/', source) or any(
            part in ('', '.', '..') for part in source[1:-1].split('/')):
        raise ValueError('source must be an absolute directory with a trailing slash and simple path components')
    volume = job['volume_uuid']
    if not isinstance(volume, str) or str(uuid.UUID(volume)) != volume:
        raise ValueError('volume_uuid must be a canonical Btrfs UUID')
    for name, limit in (('hour', 23), ('minute', 59)):
        if type(job[name]) is not int or not 0 <= job[name] <= limit:
            raise ValueError('invalid daily schedule')

    def read_key(name, private=False):
        value = job[name]
        if not isinstance(value, str) or not value:
            raise ValueError('key path must be a nonempty string')
        path = root/value
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 16384:
            raise ValueError('key must be a bounded regular file, not a symlink')
        if private and path.stat().st_mode & 0o077:
            raise ValueError('private client key requires mode 0600 or stricter')
        return path.read_bytes()

    prefix = struct.pack('>I', 11) + b'ssh-ed25519'
    client = read_key('client_key', private=True)
    if len(client) < 64 or not client.startswith(prefix):
        raise ValueError('client key must be a Dropbear Ed25519 private key')
    lines = read_key('host_public_key').decode('ascii').splitlines()
    if len(lines) != 1:
        raise ValueError('supply one independently verified source-server public key')
    parts = lines[0].split()
    if len(parts) < 2 or parts[0] != 'ssh-ed25519':
        raise ValueError('source-server key must be Ed25519')
    blob = base64.b64decode(parts[1], validate=True)
    if len(blob) != 51 or blob[:19] != prefix + struct.pack('>I', 32):
        raise ValueError('invalid source-server public key encoding')
    settings = "config backup 'main'\n" + ''.join(
        f"\toption {name} '{value}'\n" for name, value in
        (('host', host), ('user', user), ('source', source), ('volume_uuid', volume)))
    fstab = ("config global\n\toption anon_mount '0'\n\toption anon_swap '0'\n"
             "\toption auto_mount '0'\n\toption auto_swap '0'\n\n"
             "config mount 'backup'\n\toption target '/mnt/backup'\n"
             f"\toption uuid '{volume}'\n\toption fstype 'btrfs'\n"
             "\toption options 'rw,noatime'\n\toption enabled '1'\n")
    return {
        'etc/config/ls420d-backup': settings.encode(),
        'etc/config/fstab': fstab.encode(),
        'etc/crontabs/root': f"{job['minute']} {job['hour']} * * * /usr/sbin/ls420d-pull\n".encode(),
        'root/.ssh/backup_ed25519': client,
        'root/.ssh/known_hosts': f'{host} {parts[0]} {parts[1]}\n'.encode(),
    }
