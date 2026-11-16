"""Run entirely against disposable inventory and an in-memory DO HTTP API fixture."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from unittest.mock import patch

from digitalocean import DigitalOcean, LifecycleError, PROFILE, SIZE, TAG, label
from lifecycle import Lifecycle


RULES = {'inbound_rules': [{'protocol':'tcp', 'ports':'22', 'sources':{'addresses':['10.37.0.9/32']}}],
         'outbound_rules':[{'protocol':'tcp', 'ports':'443', 'destinations':{'addresses':['192.0.2.80/32']}}]}
POLICY = {'team_uuid':'1'*40, 'project_uuid':'4928e04c-247b-49d3-abeb-db8efab85c72',
          'firewall_id':'ffa328b7-e323-4ffb-ab3d-a388d600d097',
          'vpc_uuid':'e1fad327-1ef5-4b38-bb35-654a8f987754', 'image_id':284,
          'ssh_key_id':981, 'firewall_rules_sha256':sha256(json.dumps(
              RULES, sort_keys=True,separators=(',',':')).encode()).hexdigest()}


class FakeDO(DigitalOcean):
    def __init__(self):
        super().__init__('fixture', POLICY)
        self.objects = {}
        self.account_team = self.policy['team_uuid']
        self.now = 1800000000
        self.history = []
        self.extra = []
        self.cost = 0.042
        self.hidden = False
        self.post_timeout = False
        self.delete_timeout = False
        self.delete_refusal = False
        self.get_denied = False
        self.rules = deepcopy(RULES)
        self.other_firewalls = []
        self.removed = []
        self.membership = True

    def request(self, method, path, *, body=None, missing_ok=False):
        path = path.split('?')[0]
        self.history.append((method,path))
        if path == '/account':
            return {'account': {'team': {'uuid': self.account_team}, 'status':'active'}}
        if path == '/projects/default':
            return {'project':{'id':self.policy['project_uuid'], 'is_default':True, 'environment':'Staging'}}
        if path.endswith('/resources'):
            return {'resources':[{'urn':'do:droplet:'+str(i), 'status':'ok'} for i in self.objects
                                 if not self.hidden and self.membership]}
        if path.startswith('/vpcs/'):
            return {'vpc':{'id':self.policy['vpc_uuid'], 'region':'sfo3','default':False,'ip_range':'10.37.0.0/24'}}
        if path == '/firewalls':
            return {'firewalls':[{'id':self.policy['firewall_id'],'tags':[TAG]}, *self.other_firewalls]}
        if path.startswith('/firewalls/'):
            return {'firewall':{'id':self.policy['firewall_id'],'status':'succeeded','tags':[TAG],
                                'droplet_ids':[],**self.rules}}
        if path == '/sizes':
            return {'sizes':[{'slug':SIZE,'vcpus':2,'memory':4096,'disk':80,'available':True,
                              'regions':['sfo3'],'price_hourly':self.cost}]}
        if path.startswith('/images/'):
            return {'image':{'id':self.policy['image_id'],'slug':'ubuntu-22-04-x64','public':True,
                             'distribution':'Ubuntu','status':'available','regions':['sfo3']}}
        if path in ('/snapshots','/volumes','/reserved_ips'):
            return {path[1:]:self.extra if path=='/volumes' else []}
        if path.endswith('/firewalls'):
            return {'firewalls':[{'id':self.policy['firewall_id']}]}
        if path.endswith('/destroy_with_associated_resources'):
            return dict(snapshots=[],volumes=self.extra,volume_snapshots=[],reserved_ips=[])
        if path == '/droplets' and method=='POST':
            if not body['ssh_keys']==[981] or body['backups'] or body['ipv6']:
                raise AssertionError('unexpected allocation')
            self.objects[27]={'id':27,'name':body['name'],'tags':body['tags'],'size_slug':SIZE,
                              'region':{'slug':'sfo3'},'image':{'id':body['image']},'vpc_uuid':body['vpc_uuid'],
                              'vcpus':2,'memory':4096,'disk':80,'created_at':datetime.fromtimestamp(
                                  self.now,timezone.utc).isoformat(), 'status':'active',
                              'networks':{'v4':[{'type':'private','ip_address':'10.37.0.10'}]},
                              'features':[],'volume_ids':[],'snapshot_ids':[],'backup_ids':[]}
            if self.post_timeout:
                raise LifecycleError('provider_communication')
            return {'droplet':{'id':27}}
        if path == '/droplets':
            return {'droplets':[] if self.hidden else list(self.objects.values())}
        if path.startswith('/droplets/'):
            number = int(path.split('/')[-1])
            if method == 'DELETE':
                if self.delete_refusal:
                    raise LifecycleError('provider_http_403')
                self.objects.pop(number)
                self.removed.append(number)
                if self.delete_timeout:
                    raise LifecycleError('provider_communication')
                return {}
            if self.get_denied:
                raise LifecycleError('provider_http_403')
            if number in self.objects and not self.hidden:
                return {'droplet':self.objects[number]}
            if missing_ok:
                return None
        raise AssertionError((method,path))


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name)/'ledger.sqlite'
        self.p = FakeDO()
        self.l = self.restart()
        self.row = self.l.reserve('215','a'*40,PROFILE)

    def restart(self, prove=None):
        return Lifecycle(self.path,self.p,prove,now=lambda:self.p.now,sleep=lambda sec:None)

    def create(self):
        return self.l.allocate('215',user_data='#cloud-config\n',ssh_keys=[981])

    def test_happy_path_and_replay_refusals(self):
        self.assertEqual(self.create()['id'],27)
        self.assertEqual(self.l.current('215')['state'],'owned')
        with self.assertRaises(LifecycleError):
            self.l.reserve('216','a'*40,PROFILE)
        self.assertEqual(self.l.sweep(),[])
        self.assertEqual(self.l.cleanup('215')['state'],'closed')
        self.assertEqual(self.restart().cleanup('215')['state'],'closed')
        self.assertEqual(self.p.removed,[27])
        self.assertIn(('GET','/droplets/27'),self.p.history[self.p.history.index(('DELETE','/droplets/27'))+1:])
        with self.assertRaises(LifecycleError):
            self.l.reserve('215','a'*40,PROFILE)
        self.l.reserve('216','a'*40,PROFILE)

    def test_timeout_without_receipt_never_reposts(self):
        self.p.post_timeout=True
        with self.assertRaises(LifecycleError): self.create()
        with self.assertRaisesRegex(LifecycleError,'unverified'): self.create()
        with self.assertRaisesRegex(LifecycleError,'independent'): self.l.cleanup('215')
        self.assertEqual(self.p.history.count(('POST','/droplets')),1)
        self.assertEqual(self.p.removed,[])
        resumed=self.restart(lambda row,obj: row['installation_id']==self.row['installation_id'] and obj['id']==27)
        self.assertEqual(resumed.sweep(),[{'run_id':'215','state':'closed','droplet_id':27}])
        self.assertEqual(self.p.removed,[27])

    def test_duplicate_candidates_quarantine_even_with_receipt(self):
        self.create()
        self.p.objects[28]=dict(self.p.objects[27],id=28)
        with self.assertRaisesRegex(LifecycleError,'multiple_candidates'): self.l.cleanup('215')
        self.assertEqual(self.p.removed,[])
        self.assertEqual(json.loads(self.l.current('215')['candidates']),[27,28])

    def test_another_firewall_with_same_tag_blocks_creation(self):
        self.p.other_firewalls = [{'id':'foreign', 'tags':[TAG]}]
        with self.assertRaisesRegex(LifecycleError,'overlapping_staging_firewalls'): self.create()
        self.assertNotIn(('POST','/droplets'),self.p.history)

    def test_foreign_resource_and_inventory_drift(self):
        self.create()
        self.p.membership=False
        with self.assertRaisesRegex(LifecycleError,'membership'): self.l.cleanup('215')
        self.p.membership=True
        self.p.objects[27]['name']='different'
        with self.assertRaisesRegex(LifecycleError,'identity'): self.l.cleanup('215')
        self.assertEqual(self.p.removed,[])

    def test_extra_attachments_remain_for_manual_review(self):
        self.create()
        self.p.extra=[{'id':'a47970d4-2b2f-4c32-a99d-a87b31b94e7d','name':'do-not-export-this'}]
        with self.assertRaisesRegex(LifecycleError,'associated_resources'): self.l.cleanup('215')
        self.assertEqual(self.l.current('215')['reason'],'associated_resources_unresolved')
        self.assertEqual(json.loads(self.l.current('215')['ancillary']),
                         [{'type':'volumes','id':self.p.extra[0]['id']}])
        self.assertEqual(self.p.removed,[])
        with self.assertRaises(LifecycleError): self.l.reserve('216','a'*40,PROFILE)

    def test_canceled_before_and_after_bootstrap(self):
        self.assertEqual(self.l.cleanup('215')['state'],'closed')
        self.l.reserve('222','a'*40,PROFILE)
        self.l.allocate('222',user_data='fixture',ssh_keys=[981])
        # Runner goes away with no finally step. An independent process uses the durable record.
        self.p.now+=7200
        self.assertEqual(self.restart().sweep(),[{'run_id':'222','state':'closed','droplet_id':27}])

    def test_delayed_visibility_is_not_confirmed_deletion(self):
        self.p.hidden=True
        with self.assertRaises(LifecycleError): self.create()
        with self.assertRaisesRegex(LifecycleError,'absence_unconfirmed'): self.l.cleanup('215')
        self.assertEqual(self.p.removed,[])
        self.p.hidden=False
        self.assertEqual(self.restart().sweep()[0]['state'],'closed')
        self.assertEqual(self.p.removed,[27])

    def test_api_denial_never_counted_as_absence(self):
        self.create()
        self.p.get_denied=True
        with self.assertRaisesRegex(LifecycleError,'403'): self.l.cleanup('215')
        self.assertEqual(self.p.removed,[])
        self.p.get_denied=False
        self.p.delete_refusal=True
        self.assertEqual(self.restart().sweep()[0]['state'],'unresolved')
        self.p.delete_refusal=False
        self.assertEqual(self.restart().sweep()[0]['state'],'closed')

    def test_timeout_after_delete_verified_without_second_delete(self):
        self.create()
        self.p.delete_timeout=True
        with self.assertRaisesRegex(LifecycleError,'communication'): self.l.cleanup('215')
        self.assertEqual(self.restart().sweep()[0]['state'],'closed')
        self.assertEqual(self.p.removed,[27])

    def test_definitive_create_rejection_released_only_if_cloud_inventory_empty(self):
        with patch.object(self.p,'create',side_effect=LifecycleError('provider_http_422')):
            with self.assertRaisesRegex(LifecycleError,'422'): self.create()
        self.assertEqual(self.l.current('215')['create_rejected'],1)
        self.p.extra=[{'id':77}]
        self.assertEqual(self.restart().sweep()[0]['state'],'unresolved')
        self.p.extra=[]
        self.assertEqual(self.restart().sweep()[0]['state'],'closed')
        self.assertEqual(self.p.removed,[])

    def test_invalid_inputs_and_preflight_failure_can_close_without_post(self):
        with self.assertRaisesRegex(LifecycleError,'unapproved_ssh_key'):
            self.l.allocate('215',user_data='fixture',ssh_keys=[75])
        self.p.cost=.055
        with self.assertRaisesRegex(LifecycleError,'cost'): self.create()
        self.assertEqual(self.l.current('215')['state'],'reserved')
        self.assertEqual(self.l.cleanup('215')['state'],'closed')
        self.assertNotIn(('POST','/droplets'),self.p.history)

    def test_wrong_team_price_firewall_expiry_before_post(self):
        self.p.account_team='foreign'
        with self.assertRaisesRegex(LifecycleError,'owner'): self.create()
        self.p.account_team=POLICY['team_uuid']
        self.p.cost=.051
        with self.assertRaisesRegex(LifecycleError,'cost'): self.create()
        self.p.cost=.042
        self.p.rules['inbound_rules'][0]['sources']['addresses']=['0.0.0.0/0']
        with self.assertRaisesRegex(LifecycleError,'drift'): self.create()
        self.p.now+=7200
        with self.assertRaisesRegex(LifecycleError,'deadline'): self.create()
        self.assertNotIn(('POST','/droplets'),self.p.history)

    def test_sweeper_rejects_changed_policy_and_stale_creation(self):
        self.create()
        self.p.policy=dict(self.p.policy,image_id=285)
        with self.assertRaisesRegex(LifecycleError,'policy_changed'): self.restart().cleanup('215')
        self.p.policy=dict(POLICY)
        self.p.objects[27]['created_at']='2000-01-01T00:00:00Z'
        with self.assertRaisesRegex(LifecycleError,'creation_time'): self.l.cleanup('215')
        self.assertEqual(self.p.removed,[])

    def test_abandoned_unseen_create_stays_reserved(self):
        self.p.post_timeout=True
        with self.assertRaises(LifecycleError): self.create()
        self.p.hidden=True
        self.p.now+=7200
        self.assertEqual(self.restart().sweep()[0]['state'],'unresolved')
        with self.assertRaises(LifecycleError): self.l.reserve('216','a'*40,PROFILE)
        self.assertNotIn(('DELETE','/droplets/27'),self.p.history)

    def test_transport_rejects_redirect_without_following_and_scrubs_error_body(self):
        with patch('digitalocean.http.client.HTTPSConnection') as ctor:
            response=ctor.return_value.getresponse.return_value
            response.status=307
            response.read.return_value=b'staging-credential-example'
            with self.assertRaisesRegex(LifecycleError,'^provider_http_307$'):
                DigitalOcean('not-a-live-token',POLICY).request('GET','/account')
            self.assertEqual(ctor.call_count,1)
            response.read.assert_not_called()
