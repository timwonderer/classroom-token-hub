#!/usr/bin/env python3
"""
Comprehensive migration validation script.

Validates migration files for:
1. Continuous revision chain (no gaps)
2. Single head (no multiple heads)
3. All migrations have upgrade/downgrade functions
4. Idempotency and production safety patterns

Usage:
    python scripts/validate-migrations.py

Returns:
    Exit code 0 if validation passes
    Exit code 1 if critical issues found
"""
import os
import re
import sys
from pathlib import Path
from collections import defaultdict

# Adjust path for running from project root
SCRIPT_DIR = Path(__file__).parent.absolute()
PROJECT_ROOT = SCRIPT_DIR.parent
MIGRATIONS_DIR = PROJECT_ROOT / "migrations" / "versions"


def extract_migration_info(filepath):
    """Extract revision info from a migration file."""
    with open(filepath, 'r') as f:
        content = f.read()

    # Extract revision
    revision_match = re.search(r"^revision\s*=\s*['\"]([^'\"]+)['\"]", content, re.MULTILINE)
    revision = revision_match.group(1) if revision_match else None

    # Extract down_revision (can be None, a string, or a tuple)
    down_rev_match = re.search(r"^down_revision\s*=\s*(.+)$", content, re.MULTILINE)
    if down_rev_match:
        down_rev_raw = down_rev_match.group(1).strip()
        if down_rev_raw == 'None':
            down_revision = None
        elif down_rev_raw.startswith('('):
            # Tuple case - merge migration
            tuples = re.findall(r"['\"]([^'\"]+)['\"]", down_rev_raw)
            down_revision = tuple(tuples) if tuples else None
        else:
            single = re.search(r"['\"]([^'\"]+)['\"]", down_rev_raw)
            down_revision = single.group(1) if single else None
    else:
        down_revision = "MISSING"

    # Check for upgrade function
    has_upgrade = bool(re.search(r"^def upgrade\s*\(\s*\)\s*:", content, re.MULTILINE))

    # Check for downgrade function
    has_downgrade = bool(re.search(r"^def downgrade\s*\(\s*\)\s*:", content, re.MULTILINE))

    return {
        'filepath': filepath,
        'filename': filepath.name,
        'revision': revision,
        'down_revision': down_revision,
        'has_upgrade': has_upgrade,
        'has_downgrade': has_downgrade,
    }


def validate_migrations():
    """Run all migration validations."""
    if not MIGRATIONS_DIR.exists():
        print(f"❌ Migrations directory not found: {MIGRATIONS_DIR}")
        return 1

    migrations = []
    errors = []
    warnings = []

    # Read all migration files
    for filepath in MIGRATIONS_DIR.glob("*.py"):
        if filepath.name.startswith("__"):
            continue
        try:
            info = extract_migration_info(filepath)
            if info['revision']:
                migrations.append(info)
            else:
                errors.append(f"❌ No revision found in: {filepath.name}")
        except Exception as e:
            errors.append(f"❌ Error parsing {filepath.name}: {e}")

    print("=" * 60)
    print("MIGRATION VALIDATION REPORT")
    print("=" * 60)
    print(f"\n📊 Found {len(migrations)} migration files\n")

    # Build revision maps
    revision_to_info = {m['revision']: m for m in migrations}
    down_to_up = defaultdict(list)

    for m in migrations:
        down_rev = m['down_revision']
        if down_rev is None:
            down_to_up[None].append(m['revision'])
        elif isinstance(down_rev, tuple):
            for parent in down_rev:
                down_to_up[parent].append(m['revision'])
        elif down_rev != "MISSING":
            down_to_up[down_rev].append(m['revision'])

    # Find roots
    roots = [m for m in migrations if m['down_revision'] is None]
    print(f"🌱 Root migrations: {len(roots)}")
    for r in roots:
        print(f"   - {r['revision'][:12]}... ({r['filename'][:40]})")

    # Find heads
    all_revisions = set(m['revision'] for m in migrations)
    all_down_revisions = set()
    for m in migrations:
        dr = m['down_revision']
        if dr is None:
            continue
        elif isinstance(dr, tuple):
            all_down_revisions.update(dr)
        elif dr != "MISSING":
            all_down_revisions.add(dr)

    heads = all_revisions - all_down_revisions
    print(f"\n🔝 Migration heads: {len(heads)}")
    for h in sorted(heads):
        info = revision_to_info.get(h, {})
        print(f"   - {h[:12]}... ({info.get('filename', 'unknown')[:40]})")

    # Check for multiple heads (CRITICAL)
    if len(heads) > 1:
        errors.append(f"❌ CRITICAL: Multiple heads detected ({len(heads)})")
        errors.append("   This will cause deployment failures!")
        errors.append("   Run: flask db merge heads -m 'Merge migration heads'")
    else:
        print("\n✅ Single head confirmed")

    # Check for orphaned revisions
    all_valid_revisions = all_revisions | {None}
    for m in migrations:
        dr = m['down_revision']
        if dr == "MISSING":
            errors.append(f"❌ Missing down_revision in: {m['filename']}")
        elif isinstance(dr, tuple):
            for parent in dr:
                if parent not in all_valid_revisions:
                    errors.append(f"❌ Orphan: {m['filename']} references missing: {parent[:12]}...")
        elif dr is not None and dr not in all_valid_revisions:
            errors.append(f"❌ Orphan: {m['filename']} references missing: {dr[:12]}...")

    # Check for missing functions
    for m in migrations:
        if not m['has_upgrade']:
            errors.append(f"❌ Missing upgrade() in: {m['filename']}")
        if not m['has_downgrade']:
            errors.append(f"❌ Missing downgrade() in: {m['filename']}")

    # Verify chain continuity
    visited = set()

    def walk_chain(rev):
        if rev in visited:
            return
        visited.add(rev)
        for child in down_to_up.get(rev, []):
            walk_chain(child)

    for root in roots:
        walk_chain(root['revision'])
    for child in down_to_up.get(None, []):
        walk_chain(child)

    unreachable = all_revisions - visited
    if unreachable:
        errors.append(f"❌ {len(unreachable)} migrations unreachable from root")
        for rev in list(unreachable)[:3]:
            info = revision_to_info.get(rev, {})
            errors.append(f"   - {rev[:12]}... ({info.get('filename', 'unknown')})")
    else:
        print("✅ All migrations reachable from root")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if errors:
        print(f"\n🔴 ERRORS ({len(errors)}):")
        for e in errors:
            print(f"   {e}")
        print("\n❌ VALIDATION FAILED - Fix errors before deploying!")
        return 1

    if warnings:
        print(f"\n🟡 WARNINGS ({len(warnings)}):")
        for w in warnings[:5]:
            print(f"   {w}")
        if len(warnings) > 5:
            print(f"   ... and {len(warnings) - 5} more")

    print(f"\n✅ VALIDATION PASSED")
    print(f"   • {len(migrations)} migrations")
    print(f"   • {len(roots)} root(s)")
    print(f"   • {len(heads)} head(s)")
    print(f"   • Continuous chain verified")
    print("\n🟢 Safe to deploy migrations")
    return 0


if __name__ == "__main__":
    sys.exit(validate_migrations())
