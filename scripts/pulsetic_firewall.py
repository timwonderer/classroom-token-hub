#!/usr/bin/env python3
"""
Pulsetic firewall management using the official DigitalOcean pydo client.

Usage:
    python3 scripts/pulsetic_firewall.py create <droplet-id> [--name NAME]
    python3 scripts/pulsetic_firewall.py update <firewall-id>
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

try:
    from pydo import Client
except ImportError as exc:  # pragma: no cover - runtime guard
    raise SystemExit(
        "pydo is required. Install with: pip install pydo"
    ) from exc


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


def unwrap_response(resp):
    if isinstance(resp, tuple) and resp:
        return resp[0]
    return resp


def load_pulsetic_ips(json_path: Path) -> Tuple[List[str], List[str]]:
    if not json_path.exists():
        raise FileNotFoundError(f"firewall-ips.json not found at {json_path}")

    with json_path.open() as handle:
        data = json.load(handle)

    pulsetic = data.get("pulsetic", {})
    ipv4 = list(pulsetic.get("ipv4", []))
    ipv6 = list(pulsetic.get("ipv6", []))

    if not ipv4 and not ipv6:
        raise ValueError("No Pulsetic IPs found in firewall-ips.json")

    return ipv4, ipv6


def load_token(cli_token: Optional[str] = None) -> str:
    if cli_token:
        return cli_token

    for env_key in ("DIGITALOCEAN_ACCESS_TOKEN", "DIGITALOCEAN_TOKEN", "DO_TOKEN"):
        token = os.getenv(env_key)
        if token:
            return token

    config_paths = [
        Path.home() / ".config" / "doctl" / "config.yaml",
        Path.home() / ".config" / "doctl" / "config.yml",
        Path.home() / ".config" / "doctl" / "config.json",
    ]

    for path in config_paths:
        if not path.exists():
            continue
        try:
            if path.suffix == ".json":
                with path.open() as handle:
                    data = json.load(handle)
                token = data.get("access-token") or data.get("access_token")
                if token:
                    return token
            else:
                for line in path.read_text().splitlines():
                    if line.strip().startswith("access-token:"):
                        return line.split(":", 1)[1].strip().strip("'\"")
        except (OSError, json.JSONDecodeError):
            continue

    raise SystemExit(
        "DigitalOcean token not found. Set DIGITALOCEAN_ACCESS_TOKEN "
        "or authenticate doctl to generate ~/.config/doctl/config.yaml."
    )


def get_client(token: str) -> Client:
    return Client(token=token)


def build_inbound_rules(addresses: Iterable[str]) -> List[dict]:
    return [
        {
            "protocol": "tcp",
            "ports": "443",
            "sources": {"addresses": [address]},
        }
        for address in addresses
    ]


def extract_existing_addresses(inbound_rules: Sequence[dict]) -> set:
    existing = set()
    for rule in inbound_rules:
        if rule.get("protocol") != "tcp" or rule.get("ports") != "443":
            continue
        sources = rule.get("sources", {})
        for address in sources.get("addresses", []):
            existing.add(address)
    return existing


def create_firewall(client: Client, droplet_id: int, name: str, addresses: Sequence[str]) -> str:
    payload = {
        "name": name,
        "inbound_rules": build_inbound_rules(addresses),
        "outbound_rules": DEFAULT_OUTBOUND_RULES,
        "droplet_ids": [droplet_id],
    }

    resp = unwrap_response(client.firewalls.create(body=payload))
    firewall = resp.get("firewall", resp)
    firewall_id = firewall.get("id")
    if not firewall_id:
        raise RuntimeError("Failed to create firewall: missing firewall ID in response")
    return firewall_id


def update_firewall(client: Client, firewall_id: str, addresses: Sequence[str]) -> int:
    resp = unwrap_response(client.firewalls.get(firewall_id))
    firewall = resp.get("firewall", resp)
    inbound_rules = firewall.get("inbound_rules", [])
    existing = extract_existing_addresses(inbound_rules)
    missing = [address for address in addresses if address not in existing]

    if not missing:
        return 0

    payload = {"inbound_rules": build_inbound_rules(missing)}
    unwrap_response(client.firewalls.add_rules(firewall_id, body=payload))
    return len(missing)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage Pulsetic firewall rules.")
    parser.add_argument("--token", help="DigitalOcean API token")
    parser.add_argument(
        "--ips-file",
        default=str(Path(__file__).with_name("firewall-ips.json")),
        help="Path to firewall-ips.json",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create a Pulsetic firewall")
    create.add_argument("droplet_id", type=int)
    create.add_argument(
        "--name",
        default=os.getenv("PULSETIC_FIREWALL_NAME", "pulsetic"),
        help="Firewall name (default: pulsetic)",
    )

    update = subparsers.add_parser("update", help="Update an existing firewall")
    update.add_argument("firewall_id")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    token = load_token(args.token)
    client = get_client(token)

    ipv4, ipv6 = load_pulsetic_ips(Path(args.ips_file))
    addresses = ipv4 + ipv6

    if args.command == "create":
        print("Creating Pulsetic firewall via pydo...")
        firewall_id = create_firewall(client, args.droplet_id, args.name, addresses)
        print(f"OK: Firewall created: {firewall_id}")
        return

    if args.command == "update":
        print(f"Updating Pulsetic firewall {args.firewall_id} via pydo...")
        added = update_firewall(client, args.firewall_id, addresses)
        print(f"OK: Added {added} Pulsetic rules")
        return

    raise SystemExit("Unknown command")


if __name__ == "__main__":
    main()
