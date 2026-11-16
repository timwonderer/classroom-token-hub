"""Offline host enrollment, credential isolation, exact B2 dispatch and receipt tests."""
import base64
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

import bootstrap


class GuestTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve()
        self.inputs = root/"inputs"/"123"
        self.inputs.mkdir(parents=True)
        self.state = root/"state"/"123"
        self.state.parent.mkdir(mode=0o700)
        self.repo = root/"repo"
        self.repo.mkdir()
        def git(*args):
            return subprocess.check_output(["git","-C",self.repo,*args],stderr=subprocess.DEVNULL).decode().strip()
        git("init","-q")
        (self.repo/"fixture").write_text("offline release")
        git("add","fixture")
        git("-c","user.name=Fixture","-c","user.email=test@example.invalid","commit","-qm","offline")
        self.sha = git("rev-parse","HEAD")
        git("bundle","create",self.inputs/"release.bundle","HEAD")
        self.iid = "6b9c12c2-13ea-4d91-9ae4-fe7e9002c363"
        self.prepared = bootstrap.Prepared(self.inputs,self.state,self.iid,self.sha,time.time()+1800)
        self.fixture("connector",b"synthetic connector")
        self.fixture("acceptance.sh",b"exit 0")
        self.fixture("origin.crt",b"fixture cert")
        self.fixture("origin.key",b"fixture key")
        self.fixture("tunnel.token",b"synthetic-private-connector-token")
        self.providers = {key:"synthetic-"+key for key in bootstrap.b2_runtime.PROVIDERS}
        self.fixture("integration.json",self.providers)
        self.fixture("acceptance.json",{"CF-Access-Client-Id":"synthetic-client-id-0001","CF-Access-Client-Secret":"synthetic-pair-secret-0001"})
        self.cfg = {"release_sha":self.sha,"hostname":"app.stage.invalid","admission_hostname":"gate.stage.invalid",
                    "allowed_hosts":["app.stage.invalid","gate.stage.invalid","marketing.stage.invalid","api.stage.invalid"],
                    "marketing_url":"https://marketing.stage.invalid","passwordless_url":"https://api.stage.invalid",
                    "bundle_sha256":bootstrap.digest(self.inputs/"release.bundle"),
                    "connector_sha256":bootstrap.digest(self.inputs/"connector"),
                    "acceptance_sha256":bootstrap.digest(self.inputs/"acceptance.sh")}
        self.fixture("authority.json",self.cfg)
        (self.inputs/"release.bundle").chmod(0o600)
        # Translate operator ownership only; actual file mode, inode and path checks stay active.
        original=bootstrap.protected
        owner=patch.object(bootstrap,"protected",side_effect=lambda p,d,u:original(p,d,os.geteuid()))
        owner.start()
        self.addCleanup(owner.stop)
        self.host_key="ssh-ed25519 "+base64.b64encode(b"\0\0\0\x0bssh-ed25519\0\0\0\x20"+b"h"*32).decode()

    def fixture(self,name,content):
        p=self.inputs/name
        p.write_bytes(content if isinstance(content,bytes) else json.dumps(content).encode())
        p.chmod(0o600)

    def test_public_only_cloud_config_and_private_per_run_client(self):
        cloud=self.prepared.cloud_init()
        self.assertEqual(cloud,self.prepared.cloud_init())
        boot=json.loads(cloud.split("\n",1)[1])
        self.assertFalse(boot["ssh_pwauth"])
        self.assertTrue(boot["ssh_deletekeys"])
        self.assertIn("restrict ssh-ed25519 ",cloud)
        for raw in [*self.providers.values(),"fixture key","synthetic-private-connector-token","PRIVATE KEY"]:
            self.assertNotIn(raw,cloud)
        self.assertEqual((self.state/"client").stat().st_mode & 0o777,0o600)
        self.prepared.cleanup()
        self.assertEqual(list(self.state.iterdir()),[])

    def test_wrong_host_metadata_or_reservation_never_proves_ownership(self):
        self.prepared.cloud_init()
        self.assertFalse(self.prepared.prove("10.2.3.4",39))
        self.fixture("host-pin.json",{"installation_id":self.iid,"droplet_id":39,"host_key":self.host_key})
        with patch.object(bootstrap,"capture_ssh") as probe:
            for text in (self.iid+" 40 "+"2"*32,"other 39 "+"2"*32,self.iid+" 39 "+"0"*32):
                probe.return_value=text.encode()
                self.assertFalse(self.prepared.prove("10.2.3.4",39))
            probe.return_value=(self.iid+" 39 "+"2"*32).encode()
            self.assertTrue(self.prepared.prove("10.2.3.4",39))
            args,_,_=probe.call_args.args
            self.assertIn("StrictHostKeyChecking=yes",args)
            self.assertIn("IdentityAgent=none",args)
            self.assertIn("root@10.2.3.4",args)
            probe.reset_mock()
            self.assertFalse(self.prepared.prove("198.51.100.10",39))
            self.assertFalse(self.prepared.prove("10.2.3.4",40))
            probe.assert_not_called()

    def test_protected_files_and_approved_stage_only_destinations(self):
        for changes in (
            {"marketing_url":"https://unapproved.invalid"},
            {"hostname":"school.classroomtokenhub.com","allowed_hosts":[*self.cfg["allowed_hosts"],"school.classroomtokenhub.com"]},
            {"bundle_sha256":"0"*64}, {"acceptance_sha256":"1"*64}, {"release_sha":"a"*40},
        ):
            self.fixture("authority.json",{**self.cfg,**changes})
            with self.assertRaises(bootstrap.BootstrapError):
                self.prepared.cloud_init()
        self.fixture("authority.json",self.cfg)
        (self.inputs/"origin.key").chmod(0o644)
        with self.assertRaises(bootstrap.BootstrapError):
            self.prepared.cloud_init()
        (self.inputs/"origin.key").chmod(0o600)
        self.fixture("integration.json",{**self.providers,"DIGITALOCEAN_TOKEN":"should-never-be-forwarded"})
        with self.assertRaises(bootstrap.BootstrapError):
            self.prepared.cloud_init()

    def install_fixture(self,bad_receipt=False):
        statuses=[]
        commands=[]
        uploads={}
        p=self.prepared
        def run(argv,command,*args):
            commands.append(command)
        def capture(argv,command,timeout):
            commands.append(command)
            action,stage=command.split("install.py ")[1].split()[:2]
            receipt={"installation_id":self.iid,"release_sha":self.sha,"stage":stage,"action":action,"result":"ok"}
            if bad_receipt and stage=="database":
                receipt["raw_guest_output"]="sensitive fixture"
            return json.dumps(receipt).encode()
        with patch.object(p,"prove",return_value=True),patch.object(p,"_identity",return_value=([],"2"*32)), \
             patch.object(p,"_run",side_effect=run), patch.object(p,"_upload",side_effect=lambda a,k,v:uploads.update({k:v})), \
             patch.object(bootstrap,"capture_ssh",side_effect=capture):
            if bad_receipt:
                with self.assertRaisesRegex(bootstrap.BootstrapError,"invalid_stage_receipt"):
                    p.install("10.2.3.4",39,lambda s,v:statuses.append((s,v)))
            else:
                p.install("10.2.3.4",39,lambda s,v:statuses.append((s,v)))
        return statuses,commands,uploads

    def test_exact_canonical_commands_and_scoped_acceptance(self):
        statuses,commands,uploads=self.install_fixture()
        self.assertEqual(statuses,[(s,"ok") for s in (*bootstrap.STAGES,"acceptance")])
        actual=[c.split("python3 ",1)[1] for c in commands if "infra/self-hosting/install.py " in c]
        self.assertEqual(actual,["infra/self-hosting/install.py "+a+" "+s+" --config "+bootstrap.MANIFEST
                                 for s in bootstrap.STAGES for a in ("apply","check")])
        manifest=json.loads(uploads[bootstrap.MANIFEST])
        raw=uploads["/etc/cth/runtime.env"]
        parsed=bootstrap.b2_runtime.parse_env(raw.decode(),manifest)
        self.assertEqual(len({parsed[k] for k in bootstrap.b2_runtime.KEYS}),5)
        self.assertEqual(manifest["installation_id"],self.iid)
        self.assertIn("DynamicUser=yes",commands[-1])
        self.assertIn("LoadCredential=admission.json:",commands[-1])
        self.assertIn("CTH_PUBLIC_ORIGIN=https://app.stage.invalid",commands[-1])
        for secret in self.providers.values():
            self.assertNotIn(secret," ".join(commands))

    def test_interrupted_bootstrap_discards_untrusted_evidence_and_skips_acceptance(self):
        statuses,commands,_=self.install_fixture(True)
        self.assertEqual(statuses,[(s,"ok") for s in bootstrap.STAGES[:bootstrap.STAGES.index("database")]])
        self.assertFalse(any("DynamicUser=yes" in c for c in commands))

    def test_no_harness_without_approval_and_mismatched_revocation(self):
        self.fixture("authority.json",{**self.cfg,"acceptance_sha256":None})
        statuses,commands,_=self.install_fixture()
        self.assertNotIn(("acceptance","ok"),statuses)
        self.assertFalse(any("acceptance.sh" in c for c in commands))
        self.assertFalse(self.prepared.revoked(39))
        self.fixture("revoked.json",{"installation_id":self.iid,"droplet_id":39,"integrations_revoked":True})
        self.assertTrue(self.prepared.revoked(39))
        self.assertFalse(self.prepared.revoked(40))
        self.assertFalse(self.prepared.revoked(None))
        self.fixture("revoked.json",{"installation_id":self.iid,"droplet_id":None,"integrations_revoked":True})
        self.assertTrue(self.prepared.revoked(None))

    def test_enrollment_wait_and_receipt_bounds(self):
        self.prepared.expires=time.time()-1
        with self.assertRaisesRegex(bootstrap.BootstrapError,"lease_expired"):
            self.prepared.install("10.2.3.4",39,lambda *_:None)
        with self.assertRaisesRegex(bootstrap.BootstrapError,"oversized_guest_receipt"):
            bootstrap.capture_ssh(["/bin/sh","-c"],"printf '%05000d' 0",2)
        with self.assertRaisesRegex(bootstrap.BootstrapError,"guest_command_failed"):
            bootstrap.capture_ssh(["/bin/sh","-c"],"exit 3",2)
