#!/usr/bin/env python3
"""
Cloudflare + Pulsetic firewall management using the official DigitalOcean pydo client.

Usage:
    python3 scripts/firewall_complete.py create <droplet-id> [ssh-ip]
    python3 scripts/firewall_complete.py update <firewall-id>
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import List, Sequence, Tuple

from pulsetic_firewall import get_client, load_token, unwrap_response


MAX_INBOUND_RULES = 50
DEFAULT_OUTBOUND_RULES = [
    {
        "protocol": "tcp",
        "ports": "all",
        "destinations": {"addresses": ["0.0.0.0/0", "::/0"]},
    },
    {
        "protocol": "udp",
        "ports": "all",
        "destinations": {"addresses": ["0.0.0.0/0", "::/0"]},
    },
    {
        "protocol": "icmp",
        "destinations": {"addresses": ["0.0.0.0/0", "::/0"]},
    },
]


def load_ips(json_path: Path) -> Tuple[List[str], List[str], List[str], List[str]]:
    if not json_path.exists():
        raise FileNotFoundError(f"firewall-ips.json not found at {json_path}")

    with json_path.open() as handle:
        data = json.load(handle)

    cloudflare = data.get("cloudflare", {})
    pulsetic = data.get("pulsetic", {})

    cf_ipv4 = list(cloudflare.get("ipv4", []))
    cf_ipv6 = list(cloudflare.get("ipv6", []))
    pul_ipv4 = list(pulsetic.get("ipv4", []))
    pul_ipv6 = list(pulsetic.get("ipv6", []))

    if not cf_ipv4 or not cf_ipv6:
        raise ValueError("Cloudflare IPs missing from firewall-ips.json")

    return cf_ipv4, cf_ipv6, pul_ipv4, pul_ipv6


def build_inbound_rules(
    cloudflare_ipv4: Sequence[str],
    cloudflare_ipv6: Sequence[str],
    pulsetic_ipv4: Sequence[str],
    pulsetic_ipv6: Sequence[str],
    ssh_ip: str | None,
) -> List[dict]:
    rules: List[dict] = []

    if ssh_ip:
        rules.append(
            {
                "protocol": "tcp",
                "ports": "22",
                "sources": {"addresses": [ssh_ip]},
            }
        )

    for ip in cloudflare_ipv4:
        rules.append({"protocol": "tcp", "ports": "80", "sources": {"addresses": [ip]}})
        rules.append({"protocol": "tcp", "ports": "443", "sources": {"addresses": [ip]}})

    for ip in cloudflare_ipv6:
        rules.append({"protocol": "tcp", "ports": "80", "sources": {"addresses": [ip]}})
        rules.append({"protocol": "tcp", "ports": "443", "sources": {"addresses": [ip]}})

    for ip in pulsetic_ipv4:
        rules.append({"protocol": "tcp", "ports": "443", "sources": {"addresses": [ip]}})

    for ip in pulsetic_ipv6:
        rules.append({"protocol": "tcp", "ports": "443", "sources": {"addresses": [ip]}})

    return rules


def extract_existing_rules(inbound_rules: Sequence[dict]) -> set:
    existing = set()
    for rule in inbound_rules:
        protocol = rule.get("protocol")
        ports = rule.get("ports")
        for address in rule.get("sources", {}).get("addresses", []):
            existing.add((protocol, ports, address))
    return existing


def check_rule_limit(rule_count: int) -> None:
    if rule_count <= MAX_INBOUND_RULES or os.getenv("ALLOW_RULE_OVERAGE"):
        return
    raise SystemExit(
        f"Error: This setup requires {rule_count} inbound rules, but DigitalOcean "
        f"limits firewalls to {MAX_INBOUND_RULES}. Use separate firewalls or set "
        "ALLOW_RULE_OVERAGE=1 to force."
    )


def create_firewall(
    client: Client,
    droplet_id: int,
    ssh_ip: str | None,
    cf_ipv4: Sequence[str],
    cf_ipv6: Sequence[str],
    pul_ipv4: Sequence[str],
    pul_ipv6: Sequence[str],
) -> str:
    rules = build_inbound_rules(cf_ipv4, cf_ipv6, pul_ipv4, pul_ipv6, ssh_ip)
    check_rule_limit(len(rules))

    payload = {
        "name": "cloudflare-pulsetic-firewall",
        "inbound_rules": rules,
        "outbound_rules": DEFAULT_OUTBOUND_RULES,
        "droplet_ids": [droplet_id],
    }

    resp = unwrap_response(client.firewalls.create(body=payload))
    firewall = resp.get("firewall", resp)
    firewall_id = firewall.get("id")
    if not firewall_id:
        raise RuntimeError("Failed to create firewall: missing firewall ID in response")
    return firewall_id


def update_firewall(
    client,
    firewall_id: str,
    cf_ipv4: Sequence[str],
    cf_ipv6: Sequence[str],
    pul_ipv4: Sequence[str],
    pul_ipv6: Sequence[str],
) -> int:
    desired = build_inbound_rules(cf_ipv4, cf_ipv6, pul_ipv4, pul_ipv6, None)
    check_rule_limit(len(desired))

    resp = unwrap_response(client.firewalls.get(firewall_id))
    firewall = resp.get("firewall", resp)
    existing = extract_existing_rules(firewall.get("inbound_rules", []))

    missing = [
        rule
        for rule in desired
        if (rule.get("protocol"), rule.get("ports"), rule["sources"]["addresses"][0])
        not in existing
    ]

    if not missing:
        return 0

    payload = {"inbound_rules": missing}
    unwrap_response(client.firewalls.add_rules(firewall_id, body=payload))
    return len(missing)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage Cloudflare + Pulsetic firewall.")
    parser.add_argument("--token", help="DigitalOcean API token")
    parser.add_argument(
        "--ips-file",
        default=str(Path(__file__).with_name("firewall-ips.json")),
        help="Path to firewall-ips.json",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create a combined firewall")
    create.add_argument("droplet_id", type=int)
    create.add_argument("ssh_ip", nargs="?", default=None)

    update = subparsers.add_parser("update", help="Update an existing firewall")
    update.add_argument("firewall_id")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    token = load_token(args.token)
    client = get_client(token)

    cf_ipv4, cf_ipv6, pul_ipv4, pul_ipv6 = load_ips(Path(args.ips_file))

    if args.command == "create":
        firewall_id = create_firewall(
            client,
            args.droplet_id,
            args.ssh_ip,
            cf_ipv4,
            cf_ipv6,
            pul_ipv4,
            pul_ipv6,
        )
        print(f"OK: Firewall created: {firewall_id}")
        return

    if args.command == "update":
        added = update_firewall(client, args.firewall_id, cf_ipv4, cf_ipv6, pul_ipv4, pul_ipv6)
        print(f"OK: Added {added} rules")
        return

    raise SystemExit("Unknown command")


if __name__ == "__main__":
    main()
