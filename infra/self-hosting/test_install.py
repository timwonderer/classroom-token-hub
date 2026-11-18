"""Targeted portable installer checks. Run with python3 -m unittest discover -s infra/self-hosting."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import host
import install


def manifest():
    cfg = json.loads(Path(__file__).with_name('installation.example.json').read_text())
    cfg.update(machine_id='1'*32, release_sha='2'*40, installation_id='12345678-1234-4123-9234-123456789abc')
    return cfg


class ManifestTests(unittest.TestCase):
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

    def test_proxy_mode_must_be_explicit(self):
        cfg = dict(manifest(), ingress_mode="cloudflare-proxy", origin_client_ca="/etc/cth/origin-client-ca.crt")
        self.assertEqual(install.parse_manifest(json.dumps(cfg)), cfg)
        with self.assertRaisesRegex(ValueError, "invalid ingress mode"):
            install.parse_manifest(json.dumps(dict(cfg, ingress_mode="public")))

    def test_proxy_requires_separate_client_ca(self):
        cfg = dict(manifest(), ingress_mode="cloudflare-proxy")
        for ca in (None, "/tmp/ca.crt", cfg["tls_cert"], "/etc/cth/ca;injection"):
            candidate = dict(cfg)
            if ca is not None:
                candidate["origin_client_ca"] = ca
            with self.subTest(ca=ca), self.assertRaises(ValueError):
                install.parse_manifest(json.dumps(candidate))
        with self.assertRaises(ValueError):
            install.parse_manifest(json.dumps(dict(manifest(), origin_client_ca="/etc/cth/ca.crt")))

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
