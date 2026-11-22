"""Targeted portable installer checks. Run with python3 -m unittest discover -s infra/self-hosting."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import host
import install


def manifest():
    cfg = json.loads(Path(__file__).with_name('installation.example.json').read_text())
    cfg.update(machine_id='1'*32, release_sha='2'*40, installation_id='12345678-1234-4123-9234-123456789abc')
    return cfg


class ManifestTests(unittest.TestCase):
    def test_host_accounts_use_valid_gecos_and_reject_foreign_ownership(self):
        cfg = manifest()
        accounts = {}

        def command(*args):
            if args[0] == 'useradd':
                comment = args[args.index('--comment') + 1]
                # passwd fields cannot contain their colon delimiter or newlines.
                self.assertNotRegex(comment, r'[:\n\r]')
                accounts[args[-1]] = SimpleNamespace(
                    pw_gecos=comment, pw_shell='/usr/sbin/nologin',
                    pw_gid=900, pw_uid=900)
            if args[:2] == ('apt-cache', 'policy'):
                return 'Candidate: 14.24-0ubuntu0.22.04.1'
            if args[0] == '/usr/bin/python3.10':
                return 'Python 3.10.12'
            if args[0] == 'dpkg-query':
                return 'ii'
            if args[:2] == ('systemctl', 'show'):
                return 'masked'
            return ''

        with TemporaryDirectory() as tmp, \
                patch.object(host, 'BASE', Path(tmp).resolve()/'cth'), \
                patch.object(host, 'command', side_effect=command), \
                patch.object(host, 'status', return_value=1), \
                patch.object(host, 'package_version', return_value='14.24-0ubuntu0.22.04.1'), \
                patch.object(host.pwd, 'getpwnam', side_effect=accounts.__getitem__), \
                patch.object(host.grp, 'getgrnam', return_value=SimpleNamespace(gr_gid=900, gr_mem=['cthapp'])):
            # Real temporary directories; only root ownership is simulated on macOS.
            original_stat = Path.stat
            def root_stat(path, *args, **kwargs):
                result = original_stat(path, *args, **kwargs)
                return SimpleNamespace(st_uid=0, st_mode=result.st_mode)
            with patch.object(Path, 'stat', root_stat):
                host.host_stage('apply', cfg)
                self.assertEqual(set(accounts), set(host.USERS))
                host.host_stage('check', cfg)
                accounts['cthapp'].pw_gecos = 'cth-foreign-installation'
                with self.assertRaisesRegex(ValueError, 'unexpected service identity'):
                    host.host_stage('check', cfg)

    def test_standalone_interpreter_is_checksum_verified_and_used_for_the_venv(self):
        cfg = dict(manifest(), python='3.14')
        archive = b'synthetic interpreter archive'
        calls = []

        def command(*args):
            calls.append(args)
            if args[0] == 'useradd':
                accounts[args[-1]] = SimpleNamespace(pw_gecos=args[args.index('--comment') + 1],
                                                     pw_shell='/usr/sbin/nologin', pw_gid=900, pw_uid=900)
            if args[0] == 'curl':
                Path(args[args.index('--output') + 1]).write_bytes(archive)
            if args[0] == 'tar':
                (Path(args[args.index('-C') + 1])/'bin').mkdir()
                (Path(args[args.index('-C') + 1])/'bin/python3.14').write_text('')
            if args[:2] == ('apt-cache', 'policy'):
                return 'Candidate: 14.24-0ubuntu0.22.04.1'
            if str(args[0]).endswith('python3.10'):
                return 'Python 3.10.12'
            if str(args[0]).endswith('python3.14'):
                return 'Python 3.14.10'
            if args[0] == 'dpkg-query':
                return 'ii'
            if args[:2] == ('systemctl', 'show'):
                return 'masked'
            return ''

        for digest, expected in (('0'*64, 'checksum mismatch'), (hashlib.sha256(archive).hexdigest(), None)):
            accounts = {}
            with self.subTest(expected=expected), TemporaryDirectory() as tmp, \
                    patch.object(host, 'BASE', Path(tmp).resolve()/'cth'), \
                    patch.dict(host.STANDALONE, {'3.14': ('https://example.invalid/python.tar.gz', digest)}), \
                    patch.object(host, 'command', side_effect=command), \
                    patch.object(host, 'status', return_value=1), \
                    patch.object(host, 'package_version', return_value='14.24-0ubuntu0.22.04.1'), \
                    patch.object(host.pwd, 'getpwnam', side_effect=lambda n: accounts[n]), \
                    patch.object(host.grp, 'getgrnam', return_value=SimpleNamespace(gr_gid=900, gr_mem=['cthapp'])):
                original_stat = Path.stat
                def root_stat(path, *args, **kwargs):
                    return SimpleNamespace(st_uid=0, st_mode=original_stat(path, *args, **kwargs).st_mode & ~0o022)
                with patch.object(Path, 'stat', root_stat):
                    if expected:
                        with self.assertRaisesRegex(ValueError, expected):
                            host.host_stage('apply', cfg)
                        self.assertFalse((host.BASE/'python').exists())
                        continue
                    host.host_stage('apply', cfg)
                    host.host_stage('check', cfg)
                    self.assertFalse((host.BASE/'python.tar.gz').exists())
                    self.assertEqual(host.interpreter(cfg)[1], host.BASE/'python/3.14/bin/python3.14')
                    self.assertEqual(host.interpreter(manifest())[1], Path('/usr/bin/python3.10'))

    def test_complete_manifest_and_rejections(self):
        cfg = manifest()
        self.assertEqual(install.parse_manifest(json.dumps(cfg)),cfg)
        for key in cfg:
            with self.subTest(key=key), self.assertRaises(ValueError):
                install.parse_manifest(json.dumps({k:v for k,v in cfg.items() if k!=key}))
        for field, value in [('machine_id','0'*32),('release_sha','main'),('database','postgres'),
                             ('database','db;DROP'),('runtime_env','/tmp/x'),('hostname','classroomtokenhub.com')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                install.parse_manifest(json.dumps({**cfg,field:value}))
        with self.assertRaises(ValueError):
            install.parse_manifest(json.dumps(cfg)[:-1]+',"release_sha":"dev"}')
        self.assertEqual(install.parse_manifest(json.dumps({**cfg,'python':'3.14'}))['python'],'3.14')
        for value in ('3.12','3.13','python3.14',''):
            with self.subTest(python=value), self.assertRaisesRegex(ValueError,'unsupported application Python'):
                install.parse_manifest(json.dumps({**cfg,'python':value}))

    def test_proxy_is_default_and_only_supported_mode(self):
        cfg = dict(manifest(), ingress_mode="cloudflare-proxy")
        self.assertEqual(install.parse_manifest(json.dumps(cfg)), cfg)
        with self.assertRaisesRegex(ValueError, "invalid ingress mode"):
            install.parse_manifest(json.dumps(dict(cfg, ingress_mode="public")))

    def test_removed_origin_client_ca_and_tunnel_are_rejected(self):
        for extra in ({"origin_client_ca": "/etc/cth/ca.crt"}, {"ingress_mode": "tunnel"}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                install.parse_manifest(json.dumps(dict(manifest(), **extra)))

    def test_interrupted_stage_requires_verified_postconditions(self):
        with TemporaryDirectory() as tmp, patch.object(install,'trusted'), patch.object(host,'check_unused_host'), patch.object(install,'dispatch') as dispatch:
            state = Path(tmp)/'state.json'
            cfg = manifest()
            dispatch.side_effect = ValueError('incomplete offline target')
            with self.assertRaises(ValueError):
                install.advance('apply','host',cfg,state)
            self.assertEqual(json.loads(state.read_text())['pending'],'host')
            dispatch.reset_mock()
            with self.assertRaises(ValueError):
                install.advance('apply','host',cfg,state)
            dispatch.assert_called_once_with('check','host',cfg)
            dispatch.reset_mock()
            dispatch.side_effect = None
            install.advance('apply','host',cfg,state)
            dispatch.assert_called_once_with('check','host',cfg)
            self.assertIn('host',json.loads(state.read_text())['done'])
            dispatch.reset_mock()
            install.advance('apply','host',cfg,state)
            dispatch.assert_called_once_with('check','host',cfg)
            for stage, target in [('redis',cfg),('postgres',{**cfg,'database':'different'})]:
                with self.assertRaises(ValueError):
                    install.advance('apply',stage,target,state)
