#!/usr/bin/env python3
"""
Add all Pulsetic IPs to DigitalOcean firewall using pydo.

Usage:
    python3 scripts/add-uptimerobot.py <firewall-id>
"""

import sys
from pathlib import Path
from pulsetic_firewall import (
    get_client,
    load_pulsetic_ips,
    load_token,
    update_firewall,
)

# ANSI colors
GREEN = '\033[0;32m'
RED = '\033[0;31m'
NC = '\033[0m'  # No Color

def main():
    if len(sys.argv) != 2:
        print(f"{RED}Error: Firewall ID required{NC}")
        print("\nUsage:")
        print(f"  python3 {sys.argv[0]} <firewall-id>")
        print("\nExample:")
        print(f"  python3 {sys.argv[0]} 954d0d9c-a8b2-4981-85ef-42982fc496a6")
        sys.exit(1)

    firewall_id = sys.argv[1]
    token = load_token()
    client = get_client(token)

    ipv4, ipv6 = load_pulsetic_ips(Path(__file__).with_name('firewall-ips.json'))
    pulsetic_ips = ipv4 + ipv6

    print(f"{GREEN}Adding {len(pulsetic_ips)} Pulsetic IPs to firewall: {firewall_id}{NC}\n")

    added = update_firewall(client, firewall_id, pulsetic_ips)
    print(f"\n{GREEN}OK: Added {added} Pulsetic rules via pydo{NC}")

if __name__ == '__main__':
    main()
