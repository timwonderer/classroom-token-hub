"""DigitalOcean operations for the single approved CTH staging profile."""
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
import http.client
import ipaddress
import json
import re
import ssl
from urllib.parse import urlencode
from uuid import UUID


PROFILE = 'sfo3-premium-amd'
REGION = 'sfo3'
SIZE = 's-2vcpu-4gb-amd'
TAG = 'cth-ephemeral-staging'
TTL = 7200
CLEANUP_MARGIN = 300
MAX_HOURLY = Decimal('0.05')


class LifecycleError(RuntimeError):
    """Only fixed, public failure classes cross the coordinator boundary."""

    def __init__(self, reason, ancillary=()):
        super().__init__(reason)
        self.ancillary = list(ancillary)[:100]


def ancillary_id(kind, value):
    # Only numeric provider identifiers, UUIDs or IP addresses enter the private ledger.
    raw = str(value)
    if re.fullmatch('[0-9]{1,20}', raw):
        return {'type': kind, 'id': raw}
    for parse in (UUID, ipaddress.ip_address):
        try:
            return {'type': kind, 'id': str(parse(raw))}
        except ValueError:
            continue
    return {'type': kind, 'id': 'unrecognized'}



def require(ok, reason):
    if not ok:
        raise LifecycleError(reason)


def exact_id(value):
    require(type(value) is int and value > 0, 'invalid_provider_id')
    return value


def label(row):
    return 'cth-' + row['installation_id'] + '-' + str(row['expires_at'])


class DigitalOcean:
    def __init__(self, token, policy):
        require(isinstance(token, str) and token and not any(ch.isspace() for ch in token), 'invalid_api_credential')
        self.token = token
        self.policy = dict(policy)
        for field in ('project_uuid', 'vpc_uuid', 'firewall_id'):
            require(str(UUID(policy[field])) == policy[field], 'invalid_provider_policy')
        require(re.fullmatch(r'[0-9a-f]{40}|[0-9a-f-]{36}', policy['team_uuid']), 'invalid_team')
        exact_id(policy['image_id'])
        require(re.fullmatch('[0-9a-f]{64}', policy['firewall_rules_sha256']), 'invalid_firewall_policy')

    def request(self, method, path, *, body=None, missing_ok=False):
        # Fixed TLS authority, no redirect handling, HTTP proxies or automatic mutation retry.
        conn = http.client.HTTPSConnection('api.digitalocean.com', timeout=12, context=ssl.create_default_context())
        try:
            conn.request(method, '/v2' + path, body=json.dumps(body) if body is not None else None,
                         headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'})
            response = conn.getresponse()
            if missing_ok and response.status == 404:
                return None
            expected = {'GET': 200, 'POST': 202, 'DELETE': 204}[method]
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
        project = self.request('GET', '/projects/default')['project']
        require(account['status'] == 'active' and account.get('team', {}).get('uuid') == self.policy['team_uuid']
                and project['id'] == self.policy['project_uuid'] and project['is_default'] is True
                and project.get('environment') in ('Development', 'Staging'), 'wrong_cloud_owner')

    def resources(self):
        resources = self.listing('/projects/' + self.policy['project_uuid'] + '/resources', 'resources')
        require(all(r.get('status') == 'ok' for r in resources), 'incomplete_project_inventory')
        return {r['urn'] for r in resources}

    def droplets(self):
        return self.listing('/droplets', 'droplets')

    def verify_empty_extras(self):
        found = []
        for path, key in (('/volumes', 'volumes'), ('/snapshots', 'snapshots'), ('/reserved_ips', 'reserved_ips')):
            for item in self.listing(path, key):
                found.append(ancillary_id(key, item.get('id', item.get('ip'))))
        if found:
            raise LifecycleError('additional_team_resources', found)

    def firewall(self):
        fw = self.request('GET', '/firewalls/' + self.policy['firewall_id'])['firewall']
        rules = {key: fw[key] for key in ('inbound_rules', 'outbound_rules')}
        require(fw['id'] == self.policy['firewall_id'] and fw['status'] == 'succeeded'
                and not fw.get('pending_changes') and fw['tags'] == [TAG] and not fw['droplet_ids'],
                'firewall_identity')
        digest = sha256(json.dumps(rules, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        require(digest == self.policy['firewall_rules_sha256'], 'firewall_rules_drift')
        for direction, peers in (('inbound_rules', 'sources'), ('outbound_rules', 'destinations')):
            require(rules[direction], 'missing_firewall_rules')
            for rule in rules[direction]:
                endpoints = rule[peers]
                addresses = endpoints.get('addresses')
                require(addresses and not any(v for k, v in endpoints.items() if k != 'addresses')
                        and all(ipaddress.ip_network(a, strict=False).prefixlen > 0 for a in addresses),
                        'unbounded_firewall')
                if direction == 'inbound_rules':
                    require(rule['protocol'] == 'tcp' and rule['ports'] == '22'
                            and all(ipaddress.ip_network(a, strict=False).is_private and
                                    ipaddress.ip_network(a, strict=False).num_addresses == 1 for a in addresses),
                            'unbounded_ingress')

    def preflight(self):
        self.identity()
        vpc = self.request('GET', '/vpcs/' + self.policy['vpc_uuid'])['vpc']
        require(vpc['id'] == self.policy['vpc_uuid'] and vpc['region'] == REGION and vpc['default'] is False,
                'wrong_vpc')
        self.firewall()
        matching = [f['id'] for f in self.listing('/firewalls', 'firewalls') if TAG in f['tags']]
        require(matching == [self.policy['firewall_id']], 'overlapping_staging_firewalls')
        sizes = [s for s in self.listing('/sizes', 'sizes') if s['slug'] == SIZE]
        require(len(sizes) == 1, 'unsupported_size_or_cost')
        size, = sizes
        price = Decimal(str(size['price_hourly']))
        require(size['vcpus'] == 2 and size['memory'] == 4096 and size['disk'] == 80 and size['available'] is True
                and REGION in size['regions'] and Decimal(0) < price <= MAX_HOURLY, 'unsupported_size_or_cost')
        image = self.request('GET', '/images/' + str(self.policy['image_id']))['image']
        require(image['id'] == self.policy['image_id'] and image['slug'] == 'ubuntu-22-04-x64'
                and image['public'] is True and image['distribution'] == 'Ubuntu'
                and image['status'] == 'available' and REGION in image['regions'], 'unapproved_image')
        require(not self.droplets() and not self.resources(), 'occupied_staging_project')
        self.verify_empty_extras()

    def validate_create_inputs(self, user_data, ssh_keys):
        require(isinstance(user_data,str) and 0 < len(user_data.encode('utf-8')) <= 65536, 'invalid_user_data')
        require(isinstance(ssh_keys, list) and all(exact_id(n) for n in ssh_keys), 'invalid_ssh_keys')
        if self.policy.get('ssh_key_id') is not None:
            require(ssh_keys == [exact_id(self.policy['ssh_key_id'])], 'unapproved_ssh_key')
        else:
            require(not ssh_keys, 'unapproved_ssh_key')
    def create(self, row, user_data, ssh_keys):
        data = self.request('POST', '/droplets', body={
            'name': label(row), 'image': self.policy['image_id'], 'size': SIZE, 'region': REGION,
            'vpc_uuid': self.policy['vpc_uuid'], 'tags': [TAG], 'ssh_keys': ssh_keys,
            'user_data': user_data, 'backups': False, 'ipv6': False, 'monitoring': False,
        })
        return exact_id(data['droplet']['id'])

    def get(self, number):
        data = self.request('GET', '/droplets/' + str(exact_id(number)), missing_ok=True)
        if data is None:
            return None
        require(data['droplet']['id'] == number, 'wrong_provider_id')
        return data['droplet']

    def verify(self, row, obj):
        number = exact_id(obj['id'])
        require(obj['name'] == label(row) and obj['tags'] == [TAG] and obj['size_slug'] == SIZE
                and obj['region']['slug'] == REGION and obj['image']['id'] == self.policy['image_id']
                and obj['vpc_uuid'] == self.policy['vpc_uuid'] and obj['vcpus'] == 2 and obj['memory'] == 4096
                and obj['disk'] == 80, 'droplet_identity_conflict')
        created = int(datetime.fromisoformat(obj['created_at'].replace('Z', '+00:00')).timestamp())
        require(row['issued_at'] - 60 <= created < row['expires_at'], 'droplet_creation_time')
        expected = 'do:droplet:' + str(number)
        project = self.resources()
        if project != {expected}:
            extra = []
            for urn in sorted(project - {expected}):
                parts = urn.split(':', 2)
                if len(parts) == 3 and parts[1] in ('droplet','floatingip','volume','snapshot','dbaas','loadbalancer'):
                    extra.append(ancillary_id(parts[1], parts[2]))
            raise LifecycleError('project_membership_conflict', extra)

    def ready(self, obj):
        if obj['status'] != 'active':
            return False
        addresses = [ipaddress.IPv4Address(n['ip_address']) for n in obj['networks']['v4'] if n['type'] == 'private']
        vpc = self.request('GET', '/vpcs/' + self.policy['vpc_uuid'])['vpc']
        require(vpc['id'] == obj['vpc_uuid'] and len(addresses) == 1 and
                addresses[0] in ipaddress.IPv4Network(vpc['ip_range']), 'wrong_private_address')
        self.firewall()
        applied = self.listing('/droplets/' + str(exact_id(obj['id'])) + '/firewalls', 'firewalls')
        require([fw['id'] for fw in applied] == [self.policy['firewall_id']], 'unconfirmed_firewall')
        return True

    def check_extras(self, obj):
        found = [ancillary_id(key, value) for key in ('snapshot_ids','volume_ids','backup_ids') for value in obj[key]]
        associated = self.request('GET', '/droplets/' + str(exact_id(obj['id'])) + '/destroy_with_associated_resources')
        require(all(isinstance(associated.get(k), list) for k in ('snapshots','volumes','volume_snapshots','reserved_ips'))
                and set(associated) <= {'snapshots','volumes','volume_snapshots','reserved_ips','floating_ips'},
                'associated_resources_unresolved')
        for key, items in associated.items():
            found.extend(ancillary_id(key, item.get('id')) for item in items)
        if found or 'backups' in obj['features']:
            raise LifecycleError('associated_resources_unresolved', found)
        self.verify_empty_extras()

    def delete(self, number):
        self.request('DELETE', '/droplets/' + str(exact_id(number)))
