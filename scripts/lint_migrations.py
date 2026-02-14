#!/usr/bin/env python3
"""
Migration Linter - Enforce Idempotency and Safety Best Practices

This script validates that database migrations follow the project's standards
as documented in:
  - docs/development/migration-specifications.md
  - .claude/rules/database-migrations.md

Usage:
    # Lint all migrations
    python scripts/lint_migrations.py

    # Lint specific migration
    python scripts/lint_migrations.py migrations/versions/abc123_migration.py

    # Lint with verbose output
    python scripts/lint_migrations.py --verbose

Exit Codes:
    0: All checks passed
    1: Errors found (non-idempotent or unsafe patterns)
    2: Warnings found but no errors

Reference:
    See docs/development/MIGRATION_COMPLIANCE_REVIEW.md for detailed findings.
"""

import re
import sys
import argparse
from pathlib import Path
from typing import List, Tuple, Dict

# ============================================================================
# CONFIGURATION
# ============================================================================

# Helper functions that should be present in migrations
REQUIRED_HELPERS = {
    'column_exists': 'Required for add_column operations',
    'index_exists': 'Required for create_index operations',
    'foreign_key_exists': 'Required for create_foreign_key operations',
    'table_exists': 'Required for create_table operations',
}

# Patterns that indicate unsafe migration practices
UNSAFE_PATTERNS = [
    (
        r'op\.create_table\s*\(',
        'create_table without table_exists check',
        'CRITICAL',
        'Wrap in: if not table_exists("table_name"):'
    ),
    (
        r'op\.add_column\s*\(',
        'add_column without column_exists check',
        'CRITICAL',
        'Wrap in: if not column_exists("table_name", "column_name"):'
    ),
    (
        r'op\.create_index\s*\(',
        'create_index without index_exists check',
        'CRITICAL',
        'Wrap in: if not index_exists("table_name", "index_name"):'
    ),
    (
        r'op\.create_foreign_key\s*\(',
        'create_foreign_key without foreign_key_exists check',
        'CRITICAL',
        'Wrap in: if not foreign_key_exists("table_name", "fk_name"):'
    ),
    (
        r'op\.drop_constraint\s*\(\s*["\'][\w_]+["\']',
        'drop_constraint with hardcoded constraint name',
        'MAJOR',
        'Use get_foreign_keys_by_column() or dynamic discovery'
    ),
    (
        r'batch_op\.add_column\s*\(',
        'batch add_column without column_exists check',
        'CRITICAL',
        'Wrap batch_alter_table in: if not column_exists(...):'
    ),
    (
        r'batch_op\.create_foreign_key\s*\(',
        'batch create_foreign_key without foreign_key_exists check',
        'CRITICAL',
        'Wrap batch_alter_table in: if not foreign_key_exists(...):'
    ),
]

# Patterns that indicate good practices (reduce false positives)
SAFE_PATTERNS = [
    r'if\s+not\s+table_exists\s*\(',
    r'if\s+not\s+column_exists\s*\(',
    r'if\s+not\s+index_exists\s*\(',
    r'if\s+not\s+foreign_key_exists\s*\(',
    r'if\s+table_exists\s*\(',  # Checking before drop
    r'if\s+column_exists\s*\(',  # Checking before drop
]

# Files to skip (merge migrations, etc.)
SKIP_PATTERNS = [
    r'merge_.*\.py$',
    r'__init__\.py$',
    r'__pycache__',
]

# ============================================================================
# LINTING LOGIC
# ============================================================================

def should_skip_file(filepath: Path) -> bool:
    """Check if file should be skipped based on patterns."""
    filename = filepath.name
    return any(re.search(pattern, filename) for pattern in SKIP_PATTERNS)


def has_helper_function(content: str, helper_name: str) -> bool:
    """Check if a helper function is defined in the migration."""
    pattern = rf'def\s+{helper_name}\s*\('
    return bool(re.search(pattern, content))


def find_unsafe_operations(content: str, filepath: Path) -> List[Dict]:
    """Find unsafe operations that lack idempotency checks."""
    issues = []

    for pattern, message, severity, fix in UNSAFE_PATTERNS:
        matches = re.finditer(pattern, content)

        for match in matches:
            line_num = content[:match.start()].count('\n') + 1

            # Check if there's a safety check nearby (within 10 lines before)
            lines_before = 10
            context_start = max(0, content.rfind('\n', 0, match.start() - 200))
            context = content[context_start:match.start()]

            # Check for any safe pattern in the context
            has_safety_check = any(
                re.search(safe_pattern, context)
                for safe_pattern in SAFE_PATTERNS
            )

            if not has_safety_check:
                # Extract the actual operation for better reporting
                op_line_start = content.rfind('\n', 0, match.start())
                op_line_end = content.find('\n', match.end())
                op_line = content[op_line_start:op_line_end].strip()

                issues.append({
                    'line': line_num,
                    'severity': severity,
                    'message': message,
                    'fix': fix,
                    'code': op_line[:80] + ('...' if len(op_line) > 80 else '')
                })

    return issues


def lint_migration(filepath: Path, verbose: bool = False) -> Tuple[List[Dict], List[Dict]]:
    """
    Lint a single migration file.

    Returns:
        tuple: (errors, warnings)
    """
    errors = []
    warnings = []

    if should_skip_file(filepath):
        if verbose:
            print(f"⏭️  Skipping {filepath.name} (merge migration or excluded)")
        return errors, warnings

    with open(filepath, 'r') as f:
        content = f.read()

    # Check if this is actually a migration file (has upgrade/downgrade)
    if 'def upgrade():' not in content:
        if verbose:
            print(f"⏭️  Skipping {filepath.name} (not a migration file)")
        return errors, warnings

    # Find unsafe operations
    unsafe_ops = find_unsafe_operations(content, filepath)

    for issue in unsafe_ops:
        if issue['severity'] == 'CRITICAL':
            errors.append(issue)
        else:
            warnings.append(issue)

    return errors, warnings


def print_issue(issue: Dict, prefix: str):
    """Print a single issue with formatting."""
    print(f"  {prefix} Line {issue['line']}: {issue['message']}")
    if issue.get('code'):
        print(f"      Code: {issue['code']}")
    print(f"      Fix: {issue['fix']}")


def main():
    parser = argparse.ArgumentParser(
        description='Lint database migrations for idempotency and safety',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Lint all migrations
  %(prog)s migrations/versions/abc123*.py    # Lint specific migration
  %(prog)s --verbose                          # Show detailed output
  %(prog)s --report                           # Show summary report

For more information, see:
  - docs/development/MIGRATION_BEST_PRACTICES.md
  - docs/development/MIGRATION_COMPLIANCE_REVIEW.md
        """
    )
    parser.add_argument(
        'files',
        nargs='*',
        help='Specific migration files to lint (default: all)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show verbose output including skipped files'
    )
    parser.add_argument(
        '-r', '--report',
        action='store_true',
        help='Show summary report at the end'
    )

    args = parser.parse_args()

    # Determine which files to lint
    if args.files:
        migrations = [Path(f) for f in args.files]
    else:
        migrations_dir = Path('migrations/versions')
        if not migrations_dir.exists():
            print(f"❌ Error: Migration directory not found: {migrations_dir}")
            print("   Run this script from the project root directory")
            sys.exit(2)

        migrations = sorted(migrations_dir.glob('*.py'))

    if not migrations:
        print("❌ No migration files found")
        sys.exit(2)

    print(f"🔍 Linting {len(migrations)} migration files...\n")

    # Lint all migrations
    total_errors = 0
    total_warnings = 0
    files_with_errors = []
    files_with_warnings = []

    for migration_file in migrations:
        if not migration_file.exists():
            print(f"❌ File not found: {migration_file}")
            continue

        errors, warnings = lint_migration(migration_file, args.verbose)

        if errors:
            files_with_errors.append(migration_file.name)
            print(f"\n❌ {migration_file.name}")
            for error in errors:
                print_issue(error, "ERROR:")
                total_errors += 1

        elif warnings:
            files_with_warnings.append(migration_file.name)
            print(f"\n⚠️  {migration_file.name}")
            for warning in warnings:
                print_issue(warning, "WARNING:")
                total_warnings += 1

    # Print summary
    print(f"\n{'='*70}")
    print(f"📊 Summary:")
    print(f"   Total files: {len(migrations)}")
    print(f"   Files with errors: {len(files_with_errors)}")
    print(f"   Files with warnings: {len(files_with_warnings)}")
    print(f"   Total errors: {total_errors}")
    print(f"   Total warnings: {total_warnings}")

    # Print report if requested
    if args.report or total_errors > 0:
        print(f"\n{'='*70}")
        print("📋 Compliance Report:")
        print(f"\n   Idempotency: {'✅ PASS' if total_errors == 0 else '❌ FAIL'}")
        print(f"   Safety: {'✅ PASS' if total_warnings == 0 else '⚠️  WARNINGS'}")

        if total_errors > 0:
            print(f"\n   ❌ {len(files_with_errors)} files have CRITICAL issues:")
            for filename in files_with_errors[:10]:  # Show first 10
                print(f"      - {filename}")
            if len(files_with_errors) > 10:
                print(f"      ... and {len(files_with_errors) - 10} more")

        if total_warnings > 0:
            print(f"\n   ⚠️  {len(files_with_warnings)} files have warnings:")
            for filename in files_with_warnings[:10]:  # Show first 10
                print(f"      - {filename}")
            if len(files_with_warnings) > 10:
                print(f"      ... and {len(files_with_warnings) - 10} more")

    # Exit with appropriate code
    if total_errors > 0:
        print(f"\n{'='*70}")
        print("❌ Migration linting FAILED")
        print("\nTo fix these issues:")
        print("  1. Add idempotency helpers from migrations/migration_template.py.mako")
        print("  2. Wrap CREATE operations in existence checks")
        print("  3. See MIGRATION_BEST_PRACTICES.md for examples")
        print("\nOr see docs/development/MIGRATION_COMPLIANCE_REVIEW.md for full audit report")
        sys.exit(1)
    elif total_warnings > 0:
        print(f"\n{'='*70}")
        print("⚠️  Migration linting completed with warnings")
        print("   Consider fixing warnings to improve migration safety")
        sys.exit(0)
    else:
        print(f"\n{'='*70}")
        print("✅ All migrations passed linting!")
        print("   Migrations are idempotent and follow best practices")
        sys.exit(0)


if __name__ == '__main__':
    main()
