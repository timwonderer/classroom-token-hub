"""DigitalOcean operations for the single approved CTH staging profile."""

import os
import sys
import time
from decimal import Decimal
from hashlib import sha256
import http.client
import ipaddress
import json
import re
import ssl
from urllib.parse import urlencode
from uuid import UUID, uuid4

from bootstrap import runtime

REGION = 'sfo3'
SIZE = 's-2vcpu-4gb-amd'
TAG = 'cth-ephemeral-staging'
MAX_HOURLY = Decimal('0.05')


class LifecycleError(RuntimeError):
    """A fixed diagnostic safe for the workflow log."""


def require(ok, reason):
    if not ok:
        raise LifecycleError(reason)


def exact_id(value):
    require(type(value) is int and value > 0, 'invalid_provider_id')
    return value


def label(run_id, marker):
    require(re.fullmatch(r'[1-9][0-9]{0,18}', run_id), 'invalid_run')
    require(str(UUID(marker)) == marker, 'invalid_marker')
    return f'cth-{run_id}-{marker}'


class DigitalOcean:
    def __init__(self, token, policy):
        require(
            isinstance(token, str) and token and not any(ch.isspace() for ch in token), 'invalid_api_credential'
        )
        self.token = token
        self.policy = dict(policy)
        for field in ('project_uuid', 'vpc_uuid', 'firewall_id'):
            require(str(UUID(policy[field])) == policy[field], 'invalid_provider_policy')
        require(re.fullmatch(r'[0-9a-f]{40}|[0-9a-f-]{36}', policy['team_uuid']), 'invalid_team')
        exact_id(policy['image_id'])
        exact_id(policy['ssh_key_id'])
        require(re.fullmatch('[0-9a-f]{64}', policy['firewall_rules_sha256']), 'invalid_firewall_policy')

    def request(self, method, path, *, body=None, missing_ok=False):
        assignment = (method == 'POST' and path == '/projects/' + self.policy['project_uuid'] + '/resources'
                      and getattr(self, '_created_id', None) is not None
                      and body == {'resources': ['do:droplet:' + str(self._created_id)]})
        require(method == 'GET' or (method == 'POST' and path == '/droplets') or assignment,
                'unsupported_provider_operation')
        # Fixed TLS authority, no redirect handling, HTTP proxies or automatic mutation retry.
        conn = http.client.HTTPSConnection(
            'api.digitalocean.com', timeout=12, context=ssl.create_default_context()
        )
        try:
            conn.request(
                method,
                '/v2' + path,
                body=json.dumps(body) if body is not None else None,
                headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'},
            )
            response = conn.getresponse()
            if missing_ok and response.status == 404:
                return None
            expected = 200 if method == 'GET' or assignment else 202
            require(response.status == expected, 'provider_http_' + str(response.status))
            raw = response.read(2_000_001)
            require(len(raw) <= 2_000_000, 'provider_response_size')
            return json.loads(raw) if raw else {}
        except (OSError, http.client.HTTPException, ValueError):
            raise LifecycleError('provider_communication') from None
        finally:
            conn.close()

    def listing(self, path, key):
        items = []
        for page in range(1, 21):
            data = self.request('GET', path + '?' + urlencode({'page': page, 'per_page': 200}))
            require(isinstance(data[key], list), 'invalid_provider_list')
            items.extend(data[key])
            total = data.get('meta', {}).get('total')
            if not data.get('links', {}).get('pages', {}).get('next'):
                require(total is None or total == len(items), 'incomplete_provider_list')
                return items
        raise LifecycleError('provider_inventory_limit')

    def identity(self):
        account = self.request('GET', '/account')['account']
        project = self.request('GET', '/projects/' + self.policy['project_uuid'])['project']
        require(
            account['status'] == 'active'
            and account.get('team', {}).get('uuid') == self.policy['team_uuid']
            and project['id'] == self.policy['project_uuid']
            and project.get('environment') in ('Development', 'Staging'),
            'wrong_cloud_owner',
        )

    def membership(self, number):
        resources = self.listing('/projects/' + self.policy['project_uuid'] + '/resources', 'resources')
        expected = 'do:droplet:' + str(exact_id(number))
        require(
            [r.get('status') for r in resources if r['urn'] == expected] == ['ok'], 'project_membership_conflict'
        )

    def firewall(self):
        fw = self.request('GET', '/firewalls/' + self.policy['firewall_id'])['firewall']
        rules = {key: fw[key] for key in ('inbound_rules', 'outbound_rules')}
        require(
            fw['id'] == self.policy['firewall_id']
            and fw['status'] == 'succeeded'
            and not fw.get('pending_changes')
            and fw['tags'] == [TAG]
            and not fw['droplet_ids'],
            'firewall_identity',
        )
        digest = sha256(json.dumps(rules, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        require(digest == self.policy['firewall_rules_sha256'], 'firewall_rules_drift')
        for direction, peers in (('inbound_rules', 'sources'), ('outbound_rules', 'destinations')):
            require(rules[direction], 'missing_firewall_rules')
            for rule in rules[direction]:
                endpoints = rule[peers]
                addresses = endpoints.get('addresses')
                require(
                    addresses and not any(v for k, v in endpoints.items() if k != 'addresses'),
                    'unexpected_firewall_peers',
                )
                networks = [ipaddress.ip_network(a, strict=False) for a in addresses]
                if direction == 'inbound_rules':
                    require(rule['protocol'] == 'tcp' and rule['ports'] in ('22', '443'), 'unapproved_ingress')
                    if rule['ports'] == '22':
                        require(
                            self.policy.get('allow_public_ssh') is True or all(n.num_addresses == 1 for n in networks),
                            'public_ssh_not_approved',
                        )
                    else:
                        approved = [ipaddress.ip_network(net) for net in runtime.EDGE_IPV4]
                        require(all(n.version == 4 and any(n.subnet_of(a) for a in approved) for n in networks),
                                'unapproved_https_peer')
        https = {ipaddress.ip_network(a) for r in rules['inbound_rules'] if r['ports'] == '443'
                 for a in r['sources']['addresses']}
        require(https == {ipaddress.ip_network(a) for a in runtime.EDGE_IPV4}, 'missing_https_peers')

    def preflight(self):
        self.identity()
        vpc = self.request('GET', '/vpcs/' + self.policy['vpc_uuid'])['vpc']
        require(
            vpc['id'] == self.policy['vpc_uuid'] and vpc['region'] == REGION and vpc['default'] is False,
            'wrong_vpc',
        )
        self.firewall()
        matching = [f['id'] for f in self.listing('/firewalls', 'firewalls') if TAG in f['tags']]
        require(matching == [self.policy['firewall_id']], 'overlapping_staging_firewalls')
        sizes = [s for s in self.listing('/sizes', 'sizes') if s['slug'] == SIZE]
        require(len(sizes) == 1, 'unsupported_size_or_cost')
        (size,) = sizes
        price = Decimal(str(size['price_hourly']))
        require(
            size['vcpus'] == 2
            and size['memory'] == 4096
            and size['disk'] == 80
            and size['available'] is True
            and REGION in size['regions']
            and Decimal(0) < price <= MAX_HOURLY,
            'unsupported_size_or_cost',
        )
        image = self.request('GET', '/images/' + str(self.policy['image_id']))['image']
        require(
            image['id'] == self.policy['image_id']
            and image['slug'] == 'ubuntu-22-04-x64'
            and image['public'] is True
            and image['distribution'] == 'Ubuntu'
            and image['status'] == 'available'
            and REGION in image['regions'],
            'unapproved_image',
        )
        ssh_key = self.request('GET', '/account/keys/' + str(self.policy['ssh_key_id']))['ssh_key']
        require(ssh_key['id'] == self.policy['ssh_key_id'], 'unapproved_ssh_key')
        tagged = self.request('GET', '/droplets?tag_name=' + TAG + '&per_page=1')
        require(tagged['droplets'] == [] and tagged['meta']['total'] == 0, 'previous_staging_droplet')

    def get(self, number):
        data = self.request('GET', '/droplets/' + str(exact_id(number)), missing_ok=True)
        if data is None:
            return None
        require(data['droplet']['id'] == number, 'wrong_provider_id')
        return data['droplet']

    def verify(self, obj, name):
        require(
            obj['name'] == name
            and obj['tags'] == [TAG]
            and obj['size_slug'] == SIZE
            and obj['region']['slug'] == REGION
            and obj['image']['id'] == self.policy['image_id']
            and obj['vpc_uuid'] == self.policy['vpc_uuid'],
            'droplet_identity_conflict',
        )

    def create(self, run_id, output, receipt, user_data, sleep=time.sleep):
        self.preflight()
        marker = str(uuid4())
        name = label(run_id, marker)
        print(f'Allocating attended staging Droplet {name}', flush=True)
        output('marker', marker)
        # Never repeat POST on timeout, malformed JSON, cancellation, or missing ID.
        data = self.request(
            'POST',
            '/droplets',
            body={
                'name': name,
                'image': self.policy['image_id'],
                'size': SIZE,
                'region': REGION,
                'vpc_uuid': self.policy['vpc_uuid'],
                'tags': [TAG],
                'ssh_keys': [self.policy['ssh_key_id']],
                'user_data': user_data(marker),
                'backups': False,
                'ipv6': False,
                'monitoring': False,
            },
        )
        number = exact_id(data['droplet']['id'])
        print(f'Provider returned staging Droplet ID {number} for {name}', flush=True)
        output('droplet_id', str(number))
        receipt(run_id, number)
        for _ in range(24):
            obj = self.get(number)
            if obj and obj['status'] == 'active':
                self.verify(obj, name)
                self._created_id = number
                # Move only this run's receipted resource; never change the team's default project.
                self.request('POST', '/projects/' + self.policy['project_uuid'] + '/resources',
                             body={'resources': ['do:droplet:' + str(number)]})
                self.membership(number)
                self.firewall()
                applied = self.listing(f'/droplets/{number}/firewalls', 'firewalls')
                require([fw['id'] for fw in applied] == [self.policy['firewall_id']], 'unconfirmed_firewall')
                addresses = [
                    ipaddress.IPv4Address(n['ip_address']) for n in obj['networks']['v4'] if n['type'] == 'public'
                ]
                require(len(addresses) == 1 and addresses[0].is_global, 'wrong_public_address')
                output('public_ipv4', str(addresses[0]))
                return
            sleep(5)
        raise LifecycleError('readiness_timeout')

def append(path, line):
    with open(path, 'a', encoding='utf-8') as stream:
        stream.write(line + '\n')


def main():
    from bootstrap import cloud_init

    env = os.environ
    require(len(sys.argv) == 2 and sys.argv[1] == 'create', 'invalid_command')
    provider = DigitalOcean(env['DO_STAGING_TOKEN'], json.loads(env['DO_STAGING_POLICY']))
    run_id = env['GITHUB_RUN_ID']
    require(env['GITHUB_RUN_ATTEMPT'] == '1', 'rerun_requires_manual_reconciliation')
    provider.create(
        run_id,
        lambda key, val: append(env['GITHUB_OUTPUT'], f'{key}={val}'),
        lambda run, n: append(env['GITHUB_STEP_SUMMARY'], f'Staging run {run}, Droplet ID {n}'),
        cloud_init,
    )


if __name__ == '__main__':
    try:
        main()
    except LifecycleError as exc:
        sys.exit(f'Staging operation stopped ({exc}). Inspect the exact run in the staging console.')
    except (ArithmeticError, KeyError, TypeError, ValueError, OSError):
        sys.exit('Staging operation stopped. Check protected configuration and reconcile in the staging console.')
