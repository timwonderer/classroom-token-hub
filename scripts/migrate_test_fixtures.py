#!/usr/bin/env python3
"""Migrate test files from legacy Admin(username=...) to V2 make_admin() pattern.

Handles the two main cases:
1. Admin(username="...", totp_secret=...) -> make_admin("...", ...)
2. SystemAdmin(username="...", totp_secret=...) -> make_sysadmin("...", ...)
3. data={"username": admin.username, ...} -> data={"username": "<literal>", ...}
   (when admin was created with a known username string)
4. Adds conftest imports where needed
"""
import re
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).parent.parent / "tests"

# Pattern: Admin(username="<name>", ...) or Admin(username=username, ...)
ADMIN_CTOR = re.compile(
    r'Admin\(\s*username\s*=\s*([^,]+)\s*,\s*totp_secret\s*=\s*([^)]+)\)',
)
SYSADMIN_CTOR = re.compile(
    r'SystemAdmin\(\s*username\s*=\s*([^,]+)\s*,\s*totp_secret\s*=\s*([^)]+)\)',
)

# Pattern: Admin(username=f"...", ...) — f-strings
ADMIN_CTOR_F = re.compile(
    r'Admin\(\s*username\s*=\s*f(["\'])([^"\']+)\1\s*,\s*totp_secret\s*=\s*([^)]+)\)',
)
SYSADMIN_CTOR_F = re.compile(
    r'SystemAdmin\(\s*username\s*=\s*f(["\'])([^"\']+)\1\s*,\s*totp_secret\s*=\s*([^)]+)\)',
)

# Pattern: "username": admin.username  (in login data dict)
# We want to catch instances where the username was a known string in the constructor
ADMIN_USERNAME_REF = re.compile(r'"username":\s*(\w+)\.username\b')


NEEDS_CONFTEST_IMPORT = re.compile(r'from tests\.helpers\.v2_fixtures import|from v2_fixtures import')
CONFTEST_IMPORT_LINE = "from tests.helpers.v2_fixtures import make_admin, make_sysadmin\n"


def add_conftest_import(content: str, needs_admin: bool, needs_sysadmin: bool) -> str:
    """Add conftest imports if not already present."""
    if not needs_admin and not needs_sysadmin:
        return content
    
    if "from tests.helpers.v2_fixtures import" in content:
        return content

    # Add after first 'from app' or 'import' line block
    lines = content.split("\n")
    insert_at = None
    for i, line in enumerate(lines):
        if line.startswith("from app") or line.startswith("import ") or line.startswith("from tests."):
            insert_at = i
            break
    
    if insert_at is None:
        insert_at = 0
        
    lines.insert(insert_at, "from tests.helpers.v2_fixtures import make_admin, make_sysadmin")
    return "\n".join(lines)


def migrate_function_content(content: str) -> str:
    """Migrate a single function's content."""
    # Find all admin assignments in this function
    # Now catching: var = make_admin(username_var, ...)
    FIND_VAR_NAME = re.compile(r'(\w+)\s*=\s*make_admin\(([^,]+)\)')
    FIND_VAR_NAME_F = re.compile(r'(\w+)\s*=\s*make_admin\(f(["\'])([^"\']+)\3')
    
    mappings = FIND_VAR_NAME.findall(content)
    # mappings looks like [('admin', 'username'), ...] or [('admin', '"teacher1"'), ...]
    
    var_to_val = {}
    for var, val in mappings:
        val = val.strip()
        # If val is a literal string, strip quotes for easier replacement
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            var_to_val[var] = val[1:-1]
            var_to_val[var + "_is_literal"] = True
        else:
            var_to_val[var] = val
            var_to_val[var + "_is_literal"] = False

    def replace_username_ref(m):
        var = m.group(1)
        if var in var_to_val:
            val = var_to_val[var]
            if var_to_val.get(var + "_is_literal"):
                return f'"username": "{val}"'
            else:
                return f'"username": {val}'
        # Local defaults for most tests
        if var == 'admin': return '"username": "teacher1"'
        if var == 'sysadmin': return '"username": "sysadmin1"'
        return m.group(0)

    return ADMIN_USERNAME_REF.sub(replace_username_ref, content)


def migrate_file(path: Path) -> tuple[bool, str]:
    """Return (changed, new_content)."""
    original = path.read_text(encoding="utf-8")
    content = original

    # 1. Replace Constructors (Whole file)
    # CRITICAL: Replace SystemAdmin BEFORE Admin to avoid "Systemmake_admin"
    def replace_admin(m):
        username, secret = m.group(1).strip(), m.group(2).strip().rstrip(")")
        return f'make_admin({username}, {secret})'

    def replace_sysadmin(m):
        username, secret = m.group(1).strip(), m.group(2).strip().rstrip(")")
        return f'make_sysadmin({username}, {secret})'

    def replace_admin_f(m):
        quote, name, secret = m.group(1), m.group(2), m.group(3).strip().rstrip(")")
        return f'make_admin(f"{name}", {secret})'

    def replace_sysadmin_f(m):
        quote, name, secret = m.group(1), m.group(2), m.group(3).strip().rstrip(")")
        return f'make_sysadmin(f"{name}", {secret})'

    # Run SystemAdmin first
    content = SYSADMIN_CTOR_F.sub(replace_sysadmin_f, content)
    content = SYSADMIN_CTOR.sub(replace_sysadmin, content)
    # Then Admin
    content = ADMIN_CTOR_F.sub(replace_admin_f, content)
    content = ADMIN_CTOR.sub(replace_admin, content)

    # 2. Replace References (Function-by-function)
    # Split by 'def ' to handle local scopes
    parts = content.split("\ndef ")
    if len(parts) > 1:
        new_parts = [parts[0]]
        for part in parts[1:]:
            new_parts.append(migrate_function_content(part))
        content = "\ndef ".join(new_parts)
    else:
        content = migrate_function_content(content)

    # 3. Add Imports
    if "make_admin" in content or "make_sysadmin" in content:
        content = add_conftest_import(content, True, True)

    changed = content != original
    return changed, content


def main():
    test_files = sorted(TESTS_DIR.glob("test_*.py"))
    changed_count = 0
    for path in test_files:
        changed, new_content = migrate_file(path)
        if changed:
            path.write_text(new_content, encoding="utf-8")
            print(f"  MIGRATED: {path.name}")
            changed_count += 1
        else:
            print(f"  ok:       {path.name}")
    print(f"\n{changed_count}/{len(test_files)} files updated.")


if __name__ == "__main__":
    main()
