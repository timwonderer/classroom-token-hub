#!/usr/bin/env python3
"""Install or check one stage of the CTH reference host under operator authority."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys
import tempfile
from uuid import UUID

import host
import runtime

STAGES = ('host', 'postgres', 'redis', 'release', 'config', 'database', 'services', 'scheduler', 'ingress', 'readiness')
STATE = Path('/var/lib/cth-installer')
KEYS = {'installation_id', 'release_sha', 'machine_id', 'database', 'hostname', 'runtime_env', 'admission_hostname', 'tls_cert', 'tls_key'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def parse_manifest(contents):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate installation setting')
            result[key] = value
        return result
    cfg = json.loads(contents, object_pairs_hook=unique)
    require(isinstance(cfg, dict) and KEYS <= set(cfg) <= KEYS | {'ingress_mode', 'origin_client_ca'} and all(isinstance(v, str) for v in cfg.values()),
            'manifest must contain exactly the documented string fields')
    require(str(UUID(cfg['installation_id'])) == cfg['installation_id'], 'expected canonical installation UUID')
    require(re.fullmatch('[0-9a-f]{40}', cfg['release_sha']), 'expected full release SHA')
    require(re.fullmatch('[0-9a-f]{32}', cfg['machine_id']) and cfg['machine_id'] != '0' * 32, 'expected machine ID')
    require(re.fullmatch('[a-z][a-z0-9_]{0,62}', cfg['database']) and cfg['database'] not in ('postgres','template0','template1'), 'invalid database name')
    runtime.validate_config(cfg)
    return cfg


def trusted(path, mode=None):
    require(path.is_absolute() and path == path.resolve(), 'expected an absolute path without symlinks')
    for component in [*path.parents, path]:
        info = component.stat()
        require(info.st_uid == 0 and not info.st_mode & 0o022, 'operator path must be root-owned and protected')
    if mode is not None:
        require(path.is_file() and stat.S_IMODE(path.stat().st_mode) == mode, 'expected root-owned mode 0600 file')


def write_state(state, data):
    with tempfile.NamedTemporaryFile(dir=state.parent, delete=False) as f:
        f.write(json.dumps(data, sort_keys=True).encode())
        f.flush()
        os.fsync(f.fileno())
    os.replace(f.name, state)
    fd = os.open(state.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def dispatch(action, stage, cfg):
    if stage in host.STAGES:
        host.run(action, stage, cfg)
    else:
        runtime.run(action, stage, cfg)


def advance(action, stage, cfg, state):
    if not state.exists():
        require((action, stage) == ('apply', 'host'), 'first operation must apply host on a fresh target')
        host.check_unused_host(cfg)
        write_state(state, {'manifest': cfg, 'done': [], 'pending': None})
    trusted(state, 0o600)
    data = json.loads(state.read_text())
    require(data.get('manifest') == cfg, 'installation identity or manifest differs from the enrolled target')
    done = data['done']
    require(list(STAGES[:len(done)]) == done and (data['pending'] is None or data['pending'] == STAGES[len(done)]), 'invalid stage journal')
    if action == 'check' or stage in done:
        require(stage in done or data['pending'] == stage, 'stage has not started')
        dispatch('check', stage, cfg)
        return
    require(stage == STAGES[len(done)], 'complete preceding stages first')
    if data['pending'] == stage:
        # After interruption only a fully verified result can be acknowledged.
        dispatch('check', stage, cfg)
    else:
        if done:
            dispatch('check', done[-1], cfg)
        data['pending'] = stage
        write_state(state, data)
        dispatch('apply', stage, cfg)
        dispatch('check', stage, cfg)
    done.append(stage)
    data['pending'] = None
    write_state(state, data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('apply','check'))
    parser.add_argument('stage', choices=STAGES)
    parser.add_argument('--config', required=True, type=Path)
    args = parser.parse_args()
    try:
        require(os.geteuid() == 0, 'operator root required')
        os.umask(0o077)
        os.environ.clear()
        os.environ.update(PATH='/usr/sbin:/usr/bin:/sbin:/bin', LANG='C', LC_ALL='C', DEBIAN_FRONTEND='noninteractive')
        trusted(args.config, 0o600)
        cfg = parse_manifest(args.config.read_text())
        require(platform.machine() == 'x86_64' and platform.system() == 'Linux', 'expected Ubuntu x86-64')
        release = Path('/etc/os-release').read_text().splitlines()
        require('ID=ubuntu' in release and 'VERSION_ID="22.04"' in release, 'expected Ubuntu 22.04')
        require(Path('/etc/machine-id').read_text().strip() == cfg['machine_id'], 'machine identity mismatch')
        trusted(host.ROOT)
        host.verify_source(cfg)
        if args.action == 'apply' and args.stage == 'host' and not STATE.exists():
            STATE.mkdir(mode=0o700)
        trusted(STATE)
        require(STATE.is_dir() and stat.S_IMODE(STATE.stat().st_mode) == 0o700, 'unexpected installer state directory')
        fd = os.open(STATE, os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            require((STATE/'state.json').exists() or not any(STATE.iterdir()), 'unrecognized installer state directory')
            advance(args.action, args.stage, cfg, STATE/'state.json')
        finally:
            os.close(fd)
        print(json.dumps({'installation_id':cfg['installation_id'], 'release_sha':cfg['release_sha'], 'stage':args.stage, 'action':args.action, 'result':'ok'}))
    except subprocess.CalledProcessError:
        sys.exit(f'{args.stage}: external command failed; inspect local service state')
    except (ValueError, OSError, RuntimeError) as exc:
        sys.exit(f'{args.stage}: {exc}')


if __name__ == '__main__':
    main()
