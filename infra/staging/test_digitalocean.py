"""Run entirely against disposable inventory and an in-memory DO HTTP API fixture."""

from copy import deepcopy
from hashlib import sha256
import json
import unittest

from digitalocean import DigitalOcean, LifecycleError, SIZE, TAG

RULES = {
    'inbound_rules': [{'protocol': 'tcp', 'ports': '22', 'sources': {'addresses': ['10.37.0.9/32']}}],
    'outbound_rules': [{'protocol': 'tcp', 'ports': '443', 'destinations': {'addresses': ['192.0.2.80/32']}}],
}
POLICY = {
    'team_uuid': '1' * 40,
    'project_uuid': '4928e04c-247b-49d3-abeb-db8efab85c72',
    'firewall_id': 'ffa328b7-e323-4ffb-ab3d-a388d600d097',
    'vpc_uuid': 'e1fad327-1ef5-4b38-bb35-654a8f987754',
    'image_id': 284,
    'ssh_key_id': 981,
    'firewall_rules_sha256': sha256(json.dumps(RULES, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
}


class FakeDO(DigitalOcean):
    def __init__(self):
        super().__init__('fixture', POLICY)
        self.objects = {}
        self.account_team = self.policy['team_uuid']
        self.history = []
        self.cost = 0.042
        self.hidden = False
        self.post_timeout = False
        self.rules = deepcopy(RULES)
        self.other_firewalls = []
        self.is_member = True

    def request(self, method, path, *, body=None, missing_ok=False):
        path = path.split('?')[0]
        self.history.append((method, path))
        if path == '/account':
            return {'account': {'team': {'uuid': self.account_team}, 'status': 'active'}}
        if path == '/projects/default':
            return {'project': {'id': self.policy['project_uuid'], 'is_default': True, 'environment': 'Staging'}}
        if path == '/account/keys/981':
            return {'ssh_key': {'id': 981}}
        if path.endswith('/resources'):
            return {
                'resources': [{'urn': 'do:droplet:99', 'status': 'ok'}]
                + [
                    {'urn': 'do:droplet:' + str(i), 'status': 'ok'}
                    for i in self.objects
                    if not self.hidden and self.is_member
                ]
            }
        if path.startswith('/vpcs/'):
            return {
                'vpc': {
                    'id': self.policy['vpc_uuid'],
                    'region': 'sfo3',
                    'default': False,
                    'ip_range': '10.37.0.0/24',
                }
            }
        if path == '/firewalls':
            return {'firewalls': [{'id': self.policy['firewall_id'], 'tags': [TAG]}, *self.other_firewalls]}
        if path.startswith('/firewalls/'):
            return {
                'firewall': {
                    'id': self.policy['firewall_id'],
                    'status': 'succeeded',
                    'tags': [TAG],
                    'droplet_ids': [],
                    **self.rules,
                }
            }
        if path == '/sizes':
            return {
                'sizes': [
                    {
                        'slug': SIZE,
                        'vcpus': 2,
                        'memory': 4096,
                        'disk': 80,
                        'available': True,
                        'regions': ['sfo3'],
                        'price_hourly': self.cost,
                    }
                ]
            }
        if path.startswith('/images/'):
            return {
                'image': {
                    'id': self.policy['image_id'],
                    'slug': 'ubuntu-22-04-x64',
                    'public': True,
                    'distribution': 'Ubuntu',
                    'status': 'available',
                    'regions': ['sfo3'],
                }
            }
        if path.endswith('/firewalls'):
            return {'firewalls': [{'id': self.policy['firewall_id']}]}
        if path == '/droplets' and method == 'POST':
            if not body['ssh_keys'] == [981] or body['backups'] or body['ipv6']:
                raise AssertionError('unexpected allocation')
            self.objects[27] = {
                'id': 27,
                'name': body['name'],
                'tags': body['tags'],
                'size_slug': SIZE,
                'region': {'slug': 'sfo3'},
                'image': {'id': body['image']},
                'vpc_uuid': body['vpc_uuid'],
                'vcpus': 2,
                'memory': 4096,
                'disk': 80,
                'status': 'active',
                'networks': {'v4': [{'type': 'public', 'ip_address': '8.8.8.8'}]},
                'features': [],
                'volume_ids': [],
                'snapshot_ids': [],
                'backup_ids': [],
            }
            if self.post_timeout:
                raise LifecycleError('provider_communication')
            return {'droplet': {'id': 27}}
        if path == '/droplets':
            return {'droplets': list(self.objects.values()), 'meta': {'total': len(self.objects)}}
        if path.startswith('/droplets/'):
            number = int(path.split('/')[-1])
            if number in self.objects and not self.hidden:
                return {'droplet': self.objects[number]}
            if missing_ok:
                return None
        raise AssertionError((method, path))


class AttendedTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeDO()
        self.outputs = {}
        self.receipts = []

    def create(self):
        self.api.create(
            '72',
            self.outputs.__setitem__,
            lambda run, n: self.receipts.append((run, n)),
            lambda marker: '#cloud-config ' + marker,
            sleep=lambda _: None,
        )

    def test_operator_receipt_with_unrelated_project_resource(self):
        self.create()
        self.assertEqual(self.receipts, [('72', 27)])
        self.assertEqual(self.outputs['public_ipv4'], '8.8.8.8')
        self.assertEqual(self.outputs['droplet_id'], '27')
        self.assertIn(27, self.api.objects)

    def test_ambiguous_post_never_retried_or_adopted(self):
        self.api.post_timeout = True
        with self.assertRaises(LifecycleError):
            self.create()
        self.assertEqual(set(self.outputs), {'marker'})
        self.assertEqual(self.api.history.count(('POST', '/droplets')), 1)
        self.assertIn(27, self.api.objects)

    def test_interrupted_readiness_retains_exact_receipt(self):
        self.api.hidden = True
        with self.assertRaisesRegex(LifecycleError, 'readiness_timeout'):
            self.create()
        self.assertEqual(self.outputs['droplet_id'], '27')
        self.assertIn(27, self.api.objects)

    def test_existing_tag_blocks_second_create(self):
        self.create()
        with self.assertRaisesRegex(LifecycleError, 'previous_staging'):
            self.create()
        self.assertEqual(self.api.history.count(('POST', '/droplets')), 1)

    def test_provider_refuses_destructive_requests_before_connecting(self):
        with self.assertRaisesRegex(LifecycleError, 'unsupported_provider_operation'):
            DigitalOcean.request(self.api, 'DELETE', '/droplets/27')

    def test_wrong_team_blocks_allocation(self):
        self.api.account_team = 'f' * 40
        with self.assertRaisesRegex(LifecycleError, 'wrong_cloud_owner'):
            self.create()
        self.assertNotIn(('POST', '/droplets'), self.api.history)

    def test_price_and_firewall_drift_block_create(self):
        self.api.cost = 0.06
        with self.assertRaisesRegex(LifecycleError, 'cost'):
            self.create()
        self.api.cost = 0.042
        self.api.rules['inbound_rules'][0]['ports'] = '80'
        with self.assertRaisesRegex(LifecycleError, 'firewall_rules_drift'):
            self.create()
        self.assertNotIn(('POST', '/droplets'), self.api.history)

    def test_public_ssh_requires_explicit_opt_in_and_matching_rules(self):
        self.api.rules['inbound_rules'][0]['sources']['addresses'] = ['0.0.0.0/0']
        self.api.policy['firewall_rules_sha256'] = sha256(
            json.dumps(self.api.rules, sort_keys=True, separators=(',', ':')).encode()
        ).hexdigest()
        with self.assertRaisesRegex(LifecycleError, 'public_ssh_not_approved'):
            self.create()
        self.api.policy['allow_public_ssh'] = True
        self.create()

if __name__ == '__main__':
    unittest.main()
